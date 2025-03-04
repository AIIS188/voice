import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Form, Input, Button, Select, 
  Slider, Radio, Space, Upload, message, Row, Col,
  Spin, Progress
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, DownloadOutlined,
  PlayCircleOutlined, PauseCircleOutlined, SyncOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const TextToSpeech = () => {
  // 状态管理
  const [form] = Form.useForm();
  const [voiceSamples, setVoiceSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [previewSynthesizing, setPreviewSynthesizing] = useState(false);
  const [taskStatus, setTaskStatus] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [textMode, setTextMode] = useState('input'); // input, upload
  const [textContent, setTextContent] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  
  // 引用
  const audioRef = useRef(null);
  const statusCheckIntervalRef = useRef(null);
  
  // 加载声音样本数据
  const fetchVoiceSamples = async () => {
    setLoading(true);
    try {
      // 获取预设声音
      const presetVoices = [
        {
          id: 'preset_1',
          name: '男声教师1',
          description: '标准男声，适合讲解',
          tags: ['male', 'teacher', 'standard'],
          status: 'ready',
        },
        {
          id: 'preset_2',
          name: '女声教师1',
          description: '标准女声，适合讲解',
          tags: ['female', 'teacher', 'standard'],
          status: 'ready',
        },
        {
          id: 'preset_3',
          name: '男声活力',
          description: '活力男声，适合活跃气氛',
          tags: ['male', 'energetic'],
          status: 'ready',
        },
        {
          id: 'preset_4',
          name: '女声温柔',
          description: '温柔女声，适合抒情内容',
          tags: ['female', 'gentle'],
          status: 'ready',
        },
      ];
      
      // 获取用户声音样本
      try {
        const response = await axios.get('/api/voice/list');
        const userVoices = response.data.items.filter(voice => voice.status === 'ready');
        setVoiceSamples([...presetVoices, ...userVoices]);
      } catch (error) {
        console.error('获取声音样本失败:', error);
        setVoiceSamples(presetVoices);
        message.warning('获取用户声音样本失败，仅显示预设声音');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoiceSamples();
    
    // 清理函数
    return () => {
      if (statusCheckIntervalRef.current) {
        clearInterval(statusCheckIntervalRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, []);

  // 文本上传前检查
  const beforeUpload = (file) => {
    const isText = file.type === 'text/plain' || file.name.endsWith('.txt');
    if (!isText) {
      message.error('只能上传TXT文本文件!');
      return false;
    }
    const isLt2M = file.size / 1024 / 1024 < 2;
    if (!isLt2M) {
      message.error('文件必须小于2MB!');
      return false;
    }
    return true;
  };

  // 处理文本文件上传
  const handleTextUpload = async (info) => {
    if (info.file.status !== 'uploading') {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target.result;
        setTextContent(content);
        form.setFieldsValue({ text: content });
      };
      reader.readAsText(info.file.originFileObj);
    }
  };

  // 生成预览
  const handlePreview = async () => {
    try {
      const values = await form.validateFields();
      
      if (!values.text || values.text.length < 10) {
        message.error('文本内容至少需要10个字符');
        return;
      }
      
      if (!values.voice_id) {
        message.error('请选择声音');
        return;
      }
      
      setPreviewSynthesizing(true);
      
      // 提交预览请求
      const response = await axios.post('/api/tts/preview', {
        text: values.text.substring(0, 200), // 仅处理前200个字符
        voice_id: values.voice_id,
        params: {
          speed: values.speed || 1.0,
          pitch: values.pitch || 0,
          energy: values.energy || 1.0,
          emotion: values.emotion || 'neutral',
          pause_factor: values.pause_factor || 1.0,
          is_preview: true
        }
      });
      
      const taskId = response.data.task_id;
      
      // 轮询检查任务状态
      const checkStatus = async () => {
        try {
          const statusResponse = await axios.get(`/api/tts/status/${taskId}`);
          const status = statusResponse.data;
          
          if (status.status === 'completed') {
            // 下载音频
            const audioBlob = await fetchAudio(taskId);
            const url = URL.createObjectURL(audioBlob);
            
            setAudioUrl(url);
            setPreviewSynthesizing(false);
            
            // 自动播放预览
            if (audioRef.current) {
              audioRef.current.src = url;
              audioRef.current.play();
              setIsPlaying(true);
              
              audioRef.current.onended = () => {
                setIsPlaying(false);
              };
            }
            
            clearInterval(statusCheckIntervalRef.current);
          } else if (status.status === 'failed') {
            message.error('预览生成失败：' + (status.error || '未知错误'));
            setPreviewSynthesizing(false);
            clearInterval(statusCheckIntervalRef.current);
          }
        } catch (error) {
          console.error('获取任务状态失败:', error);
          message.error('获取预览任务状态失败');
          setPreviewSynthesizing(false);
          clearInterval(statusCheckIntervalRef.current);
        }
      };
      
      // 每秒检查一次状态
      statusCheckIntervalRef.current = setInterval(checkStatus, 1000);
      
      // 立即检查一次
      checkStatus();
      
    } catch (error) {
      console.error('表单验证或提交预览请求失败:', error);
      message.error('预览失败，请检查输入');
      setPreviewSynthesizing(false);
    }
  };

  // 开始合成
  const handleSynthesize = async () => {
    try {
      const values = await form.validateFields();
      
      if (!values.text || values.text.length < 10) {
        message.error('文本内容至少需要10个字符');
        return;
      }
      
      if (!values.voice_id) {
        message.error('请选择声音');
        return;
      }
      
      setSynthesizing(true);
      
      // 提交合成请求
      const response = await axios.post('/api/tts/synthesize', {
        text: values.text,
        voice_id: values.voice_id,
        params: {
          speed: values.speed || 1.0,
          pitch: values.pitch || 0,
          energy: values.energy || 1.0,
          emotion: values.emotion || 'neutral',
          pause_factor: values.pause_factor || 1.0
        }
      });
      
      const taskId = response.data.task_id;
      setTaskStatus({
        id: taskId,
        status: 'pending',
        progress: 0
      });
      
      // 轮询检查任务状态
      const checkStatus = async () => {
        try {
          const statusResponse = await axios.get(`/api/tts/status/${taskId}`);
          const status = statusResponse.data;
          
          setTaskStatus({
            id: taskId,
            status: status.status,
            progress: status.progress * 100,
            message: status.message,
            error: status.error,
            duration: status.duration
          });
          
          if (status.status === 'completed') {
            // 下载音频
            const audioBlob = await fetchAudio(taskId);
            const url = URL.createObjectURL(audioBlob);
            
            setAudioUrl(url);
            setSynthesizing(false);
            
            clearInterval(statusCheckIntervalRef.current);
          } else if (status.status === 'failed') {
            message.error('合成失败：' + (status.error || '未知错误'));
            setSynthesizing(false);
            clearInterval(statusCheckIntervalRef.current);
          }
        } catch (error) {
          console.error('获取任务状态失败:', error);
          message.error('获取合成任务状态失败');
          setSynthesizing(false);
          clearInterval(statusCheckIntervalRef.current);
        }
      };
      
      // 每2秒检查一次状态
      statusCheckIntervalRef.current = setInterval(checkStatus, 2000);
      
      // 立即检查一次
      checkStatus();
      
    } catch (error) {
      console.error('表单验证或提交合成请求失败:', error);
      message.error('合成失败，请检查输入');
      setSynthesizing(false);
    }
  };

  // 获取音频文件
  const fetchAudio = async (taskId) => {
    try {
      const response = await axios.get(`/api/tts/download/${taskId}`, {
        responseType: 'blob'
      });
      return response.data;
    } catch (error) {
      console.error('下载音频失败:', error);
      message.error('下载音频失败');
      throw error;
    }
  };

  // 下载合成结果
  const handleDownload = async () => {
    if (!taskStatus || taskStatus.status !== 'completed') {
      message.error('没有可下载的内容');
      return;
    }
    
    try {
      const audioBlob = await fetchAudio(taskStatus.id);
      const url = URL.createObjectURL(audioBlob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = `tts_${taskStatus.id}.wav`;
      document.body.appendChild(a);
      a.click();
      
      // 清理
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);
      
    } catch (error) {
      console.error('下载失败:', error);
    }
  };

  // 播放/暂停音频
  const togglePlay = () => {
    if (!audioRef.current || !audioUrl) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };

  // 监听音频播放结束
  useEffect(() => {
    const audioElement = audioRef.current;
    
    const handleEnded = () => {
      setIsPlaying(false);
    };
    
    if (audioElement) {
      audioElement.addEventListener('ended', handleEnded);
    }
    
    return () => {
      if (audioElement) {
        audioElement.removeEventListener('ended', handleEnded);
      }
    };
  }, []);

  // 渲染语音参数控制器
  const renderVoiceControls = () => (
    <div className="voice-controls">
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Form.Item
            name="speed"
            label="语速"
            initialValue={1.0}
          >
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              marks={{
                0.5: '慢',
                1.0: '正常',
                1.5: '快',
                2.0: '很快'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="pitch"
            label="音调"
            initialValue={0}
          >
            <Slider
              min={-1.0}
              max={1.0}
              step={0.1}
              marks={{
                '-1.0': '低',
                '0': '正常',
                '1.0': '高'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="energy"
            label="音量"
            initialValue={1.0}
          >
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              marks={{
                0.5: '弱',
                1.0: '中',
                1.5: '强',
                2.0: '很强'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="pause_factor"
            label="停顿"
            initialValue={1.0}
          >
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              marks={{
                0.5: '短',
                1.0: '正常',
                2.0: '长'
              }}
            />
          </Form.Item>
        </Col>
        <Col span={24}>
          <Form.Item
            name="emotion"
            label="情感风格"
            initialValue="neutral"
          >
            <Radio.Group>
              <Radio.Button value="neutral">平静</Radio.Button>
              <Radio.Button value="happy">活力</Radio.Button>
              <Radio.Button value="sad">忧伤</Radio.Button>
              <Radio.Button value="serious">严肃</Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Col>
      </Row>
    </div>
  );

  return (
    <div className="text-to-speech">
      <div className="page-header">
        <Title level={2}>个性化语音讲解</Title>
        <Paragraph>
          将文本内容转换为自然流畅的语音，可以选择不同的声音和调整各种参数。
          支持800-2000字的文本内容，可以输入或上传文本文件。
        </Paragraph>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="文本输入" bordered={false}>
            <Form form={form} layout="vertical">
              <Form.Item label="输入方式">
                <Radio.Group
                  value={textMode}
                  onChange={(e) => setTextMode(e.target.value)}
                >
                  <Radio.Button value="input">直接输入</Radio.Button>
                  <Radio.Button value="upload">上传文件</Radio.Button>
                </Radio.Group>
              </Form.Item>
              
              {textMode === 'input' ? (
                <Form.Item
                  name="text"
                  label="文本内容"
                  rules={[{ required: true, message: '请输入文本内容' }]}
                >
                  <TextArea
                    rows={10}
                    placeholder="请输入要转换为语音的文本内容，800-2000字"
                    maxLength={2000}
                    showCount
                  />
                </Form.Item>
              ) : (
                <Form.Item
                  name="text_file"
                  label="文本文件"
                  rules={[{ required: true, message: '请上传文本文件' }]}
                >
                  <Upload
                    beforeUpload={beforeUpload}
                    onChange={handleTextUpload}
                    maxCount={1}
                    showUploadList={true}
                    accept=".txt"
                  >
                    <Button icon={<UploadOutlined />}>选择文件</Button>
                    <div style={{ marginTop: 8 }}>支持TXT格式，UTF-8编码，最大2MB</div>
                  </Upload>
                </Form.Item>
              )}
              
              {textMode === 'upload' && textContent && (
                <Form.Item label="文件内容预览">
                  <TextArea
                    value={textContent.substring(0, 300) + (textContent.length > 300 ? '...' : '')}
                    rows={5}
                    readOnly
                  />
                  <div>字符数: {textContent.length}</div>
                </Form.Item>
              )}
            </Form>
          </Card>
        </Col>
        
        <Col xs={24} lg={8}>
          <Card title="声音选择" bordered={false}>
            <Form.Item
              name="voice_id"
              label="选择声音"
              required
              rules={[{ required: true, message: '请选择声音' }]}
            >
              <Select
                placeholder="请选择声音"
                loading={loading}
                style={{ width: '100%' }}
              >
                {voiceSamples.map(voice => (
                  <Option key={voice.id} value={voice.id}>
                    {voice.name} {voice.tags ? `(${voice.tags.join(', ')})` : ''}
                  </Option>
                ))}
              </Select>
            </Form.Item>
            
            <div style={{ marginBottom: 16 }}>
              <Text>没有合适的声音？</Text>
              <Button type="link" href="/voice-library">前往声音样本库</Button>
            </div>
            
            <div className="audio-preview">
              <Card
                size="small"
                title="音频预览"
                extra={
                  <Space>
                    {audioUrl && (
                      <Button
                        type="text"
                        icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                        onClick={togglePlay}
                        disabled={previewSynthesizing}
                      />
                    )}
                    <Button
                      type="primary"
                      size="small"
                      onClick={handlePreview}
                      loading={previewSynthesizing}
                      disabled={synthesizing}
                    >
                      生成预览
                    </Button>
                  </Space>
                }
              >
                {previewSynthesizing ? (
                  <div style={{ textAlign: 'center', padding: '20px 0' }}>
                    <Spin tip="生成预览中..." />
                  </div>
                ) : audioUrl ? (
                  <div style={{ padding: '10px 0' }}>
                    <audio ref={audioRef} src={audioUrl} style={{ width: '100%' }} controls />
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px 0', color: '#aaa' }}>
                    点击"生成预览"按钮生成音频预览
                  </div>
                )}
              </Card>
            </div>
          </Card>
        </Col>
        
        <Col span={24}>
          <Card title="语音参数" bordered={false}>
            <Form form={form} layout="vertical">
              {renderVoiceControls()}
            </Form>
          </Card>
        </Col>
        
        <Col span={24}>
          <Card bordered={false}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Space size="large">
                <Button
                  type="primary"
                  size="large"
                  icon={<AudioOutlined />}
                  onClick={handleSynthesize}
                  loading={synthesizing}
                  disabled={previewSynthesizing}
                >
                  开始合成
                </Button>
                
                <Button
                  size="large"
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                  disabled={!taskStatus || taskStatus.status !== 'completed'}
                >
                  下载结果
                </Button>
              </Space>
            </div>
            
            {/* 合成进度 */}
            {taskStatus && (
              <div style={{ marginTop: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <Text>合成进度</Text>
                  <Text>{taskStatus.status === 'completed' ? '完成' : taskStatus.status === 'failed' ? '失败' : '处理中'}</Text>
                </div>
                <Progress
                  percent={taskStatus.progress || 0}
                  status={
                    taskStatus.status === 'completed' ? 'success' :
                    taskStatus.status === 'failed' ? 'exception' : 'active'
                  }
                />
                {taskStatus.message && (
                  <div style={{ marginTop: 5 }}>
                    <Text type={taskStatus.error ? 'danger' : 'secondary'}>
                      {taskStatus.message || taskStatus.error}
                    </Text>
                  </div>
                )}
                {taskStatus.status === 'completed' && taskStatus.duration && (
                  <div style={{ marginTop: 5 }}>
                    <Text>音频时长: {taskStatus.duration.toFixed(1)}秒</Text>
                  </div>
                )}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TextToSpeech;