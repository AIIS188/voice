import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Button, Table, Tag, Space, 
  Upload, Modal, Form, Input, message, Progress, 
  Tabs
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, PlusOutlined, 
  DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined 
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph } = Typography;
const { TabPane } = Tabs;

const VoiceLibrary = () => {
  // 状态管理
  const [voiceSamples, setVoiceSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [recordModalVisible, setRecordModalVisible] = useState(false);
  const [playingId, setPlayingId] = useState(null);
  const [recordingStatus, setRecordingStatus] = useState('inactive'); // inactive, recording, paused
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedAudio, setRecordedAudio] = useState(null);
  
  // 录音相关引用
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  
  // 表单引用
  const [form] = Form.useForm();
  
  // 模拟预设的声音样本
  const presetVoices = [
    {
      id: 'preset_1',
      name: '男声教师1',
      description: '标准男声，适合讲解',
      tags: ['male', 'teacher', 'standard'],
      created_at: '2023-01-01T08:00:00Z',
      status: 'ready',
      quality_score: 0.95,
    },
    {
      id: 'preset_2',
      name: '女声教师1',
      description: '标准女声，适合讲解',
      tags: ['female', 'teacher', 'standard'],
      created_at: '2023-01-01T08:00:00Z',
      status: 'ready',
      quality_score: 0.96,
    },
    {
      id: 'preset_3',
      name: '男声活力',
      description: '活力男声，适合活跃气氛',
      tags: ['male', 'energetic'],
      created_at: '2023-01-01T08:00:00Z',
      status: 'ready',
      quality_score: 0.92,
    },
    {
      id: 'preset_4',
      name: '女声温柔',
      description: '温柔女声，适合抒情内容',
      tags: ['female', 'gentle'],
      created_at: '2023-01-01T08:00:00Z',
      status: 'ready',
      quality_score: 0.94,
    },
  ];

  // 加载声音样本数据
  const fetchVoiceSamples = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/voice/list');
      setVoiceSamples(response.data.items);
    } catch (error) {
      console.error('获取声音样本失败:', error);
      message.error('获取声音样本失败，请稍后重试');
      // 用模拟数据作为后备
      setVoiceSamples([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoiceSamples();
  }, []);

  // 播放声音示例
  const playVoiceSample = (id) => {
    if (playingId === id) {
      // 暂停播放
      setPlayingId(null);
      const audio = document.getElementById(`audio-${id}`);
      if (audio) audio.pause();
    } else {
      // 开始播放
      setPlayingId(id);
      const audio = document.getElementById(`audio-${id}`);
      if (audio) {
        audio.play().catch(err => {
          console.error('播放失败:', err);
          message.error('音频播放失败');
        });
        
        // 监听播放结束
        audio.onended = () => {
          setPlayingId(null);
        };
      }
    }
  };

  // 删除声音样本
  const deleteVoiceSample = async (id) => {
    try {
      await axios.delete(`/api/voice/${id}`);
      message.success('删除成功');
      fetchVoiceSamples();
    } catch (error) {
      console.error('删除失败:', error);
      message.error('删除失败，请稍后重试');
    }
  };

  // 上传声音样本
  const uploadVoiceSample = async (values) => {
    const { name, description, tags, file } = values;
    
    const formData = new FormData();
    formData.append('file', file.file.originFileObj);
    formData.append('name', name);
    formData.append('description', description || '');
    formData.append('tags', tags || '');
    
    try {
      await axios.post('/api/voice/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      message.success('上传成功');
      setUploadModalVisible(false);
      form.resetFields();
      fetchVoiceSamples();
    } catch (error) {
      console.error('上传失败:', error);
      message.error('上传失败，请稍后重试');
    }
  };

  // 开始录音
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        setRecordedAudio({ blob: audioBlob, url: audioUrl });
      };
      
      mediaRecorderRef.current.start();
      setRecordingStatus('recording');
      
      // 开始计时
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('录音失败:', error);
      message.error('无法访问麦克风，请检查设备权限');
    }
  };

  // 暂停录音
  const pauseRecording = () => {
    if (mediaRecorderRef.current && recordingStatus === 'recording') {
      mediaRecorderRef.current.pause();
      setRecordingStatus('paused');
      clearInterval(timerRef.current);
    }
  };

  // 继续录音
  const resumeRecording = () => {
    if (mediaRecorderRef.current && recordingStatus === 'paused') {
      mediaRecorderRef.current.resume();
      setRecordingStatus('recording');
      
      // 继续计时
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    }
  };

  // 停止录音
  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      setRecordingStatus('inactive');
      clearInterval(timerRef.current);
    }
  };

  // 保存录音
  const saveRecording = async (values) => {
    if (!recordedAudio) {
      message.error('请先录制声音');
      return;
    }
    
    const { name, description, tags } = values;
    
    const formData = new FormData();
    formData.append('file', new File([recordedAudio.blob], `${name}.wav`, { type: 'audio/wav' }));
    formData.append('name', name);
    formData.append('description', description || '');
    formData.append('tags', tags || '');
    
    try {
      await axios.post('/api/voice/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      message.success('保存成功');
      setRecordModalVisible(false);
      setRecordingStatus('inactive');
      setRecordingTime(0);
      setRecordedAudio(null);
      form.resetFields();
      fetchVoiceSamples();
    } catch (error) {
      console.error('保存失败:', error);
      message.error('保存失败，请稍后重试');
    }
  };

  // 重置录音
  const resetRecording = () => {
    setRecordingStatus('inactive');
    setRecordingTime(0);
    setRecordedAudio(null);
    clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  // 关闭录音弹窗
  const handleRecordModalCancel = () => {
    resetRecording();
    setRecordModalVisible(false);
  };

  // 格式化录音时间
  const formatRecordTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 判断录音时长是否在有效范围内
  const isValidRecordingLength = () => {
    return recordingTime >= 5 && recordingTime <= 30;
  };

  // 表格列定义
  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <>
          {tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        let color = 'default';
        let text = '未知';
        
        if (status === 'ready') {
          color = 'success';
          text = '可用';
        } else if (status === 'processing') {
          color = 'processing';
          text = '处理中';
        } else if (status === 'failed') {
          color = 'error';
          text = '失败';
        }
        
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '质量评分',
      dataIndex: 'quality_score',
      key: 'quality_score',
      render: (score) => score ? (score * 100).toFixed(0) + '%' : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button 
            type="text" 
            icon={playingId === record.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => playVoiceSample(record.id)}
          >
            {playingId === record.id ? '暂停' : '播放'}
          </Button>
          {/* 隐藏的音频元素 */}
          <audio 
            id={`audio-${record.id}`}
            src={`/api/voice/${record.id}/audio`} 
            style={{ display: 'none' }}
          />
          
          {record.id.startsWith('preset_') ? null : (
            <Button 
              type="text" 
              danger
              icon={<DeleteOutlined />}
              onClick={() => deleteVoiceSample(record.id)}
            >
              删除
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div className="voice-library">
      <div className="page-header">
        <Title level={2}>声音样本库</Title>
        <Paragraph>
          管理声音样本，可以使用预设声音，或者上传、录制自己的声音。
          每个声音样本需要5-30秒长度，系统会自动提取声音特征。
        </Paragraph>
      </div>

      {/* 操作按钮 */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button 
            type="primary" 
            icon={<UploadOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            上传声音
          </Button>
          <Button 
            icon={<AudioOutlined />}
            onClick={() => setRecordModalVisible(true)}
          >
            录制声音
          </Button>
        </Space>
      </div>

      {/* 声音样本列表 */}
      <Tabs defaultActiveKey="1">
        <TabPane tab="预设声音" key="1">
          <Table 
            columns={columns} 
            dataSource={presetVoices}
            rowKey="id"
            loading={loading}
          />
        </TabPane>
        <TabPane tab="我的声音" key="2">
          <Table 
            columns={columns} 
            dataSource={voiceSamples}
            rowKey="id"
            loading={loading}
          />
        </TabPane>
      </Tabs>

      {/* 上传声音弹窗 */}
      <Modal
        title="上传声音样本"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={uploadVoiceSample}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入声音名称' }]}
          >
            <Input placeholder="例如：教师男声1" />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea placeholder="对声音的描述" />
          </Form.Item>
          
          <Form.Item
            name="tags"
            label="标签"
          >
            <Input placeholder="用逗号分隔，例如：男声,清晰,教学" />
          </Form.Item>
          
          <Form.Item
            name="file"
            label="音频文件"
            rules={[{ required: true, message: '请上传音频文件' }]}
          >
            <Upload
              accept="audio/*"
              maxCount={1}
              beforeUpload={() => false}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
              <div style={{ marginTop: 8 }}>支持WAV、MP3格式，5-30秒，小于10MB</div>
            </Upload>
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setUploadModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">上传</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 录制声音弹窗 */}
      <Modal
        title="录制声音样本"
        open={recordModalVisible}
        onCancel={handleRecordModalCancel}
        footer={null}
        width={600}
      >
        <div style={{ marginBottom: 20 }}>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>
              {formatRecordTime(recordingTime)}
            </div>
            <div>
              {recordingStatus === 'inactive' && !recordedAudio && '准备录制'}
              {recordingStatus === 'recording' && '正在录制...'}
              {recordingStatus === 'paused' && '已暂停'}
              {recordingStatus === 'inactive' && recordedAudio && '录制完成'}
            </div>
          </div>
          
          {/* 录音进度条 */}
          <Progress 
            percent={Math.min(100, (recordingTime / 30) * 100)} 
            status={
              recordingTime > 30 ? 'exception' : 
              recordingTime < 5 ? 'active' : 'success'
            }
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            {recordingTime < 5 && '至少需要5秒'}
            {recordingTime > 5 && recordingTime < 30 && '长度合适'}
            {recordingTime > 30 && '已超过最大长度30秒'}
          </div>
        </div>
        
        {/* 录音控制按钮 */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          {recordingStatus === 'inactive' && !recordedAudio && (
            <Button type="primary" onClick={startRecording} icon={<AudioOutlined />}>
              开始录制
            </Button>
          )}
          
          {recordingStatus === 'recording' && (
            <>
              <Button onClick={pauseRecording} style={{ marginRight: 8 }}>
                暂停
              </Button>
              <Button type="primary" onClick={stopRecording}>
                停止录制
              </Button>
            </>
          )}
          
          {recordingStatus === 'paused' && (
            <>
              <Button type="primary" onClick={resumeRecording} style={{ marginRight: 8 }}>
                继续
              </Button>
              <Button onClick={stopRecording}>
                停止录制
              </Button>
            </>
          )}
          
          {recordingStatus === 'inactive' && recordedAudio && (
            <>
              <Button onClick={() => {
                const audio = new Audio(recordedAudio.url);
                audio.play();
              }} style={{ marginRight: 8 }}>
                播放
              </Button>
              <Button type="primary" onClick={startRecording} style={{ marginRight: 8 }}>
                重新录制
              </Button>
            </>
          )}
        </div>
        
        {/* 录音保存表单 */}
        {recordingStatus === 'inactive' && recordedAudio && (
          <Form
            form={form}
            layout="vertical"
            onFinish={saveRecording}
          >
            <Form.Item
              name="name"
              label="名称"
              rules={[{ required: true, message: '请输入声音名称' }]}
            >
              <Input placeholder="例如：我的声音1" />
            </Form.Item>
            
            <Form.Item
              name="description"
              label="描述"
            >
              <Input.TextArea placeholder="对声音的描述" />
            </Form.Item>
            
            <Form.Item
              name="tags"
              label="标签"
            >
              <Input placeholder="用逗号分隔，例如：男声,清晰,教学" />
            </Form.Item>
            
            <Form.Item>
              <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                <Button onClick={handleRecordModalCancel}>取消</Button>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  disabled={!isValidRecordingLength()}
                >
                  保存
                </Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
};

export default VoiceLibrary;