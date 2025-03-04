import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Button, Upload, message, Steps, 
  Input, Select, Slider, Form, Spin, Row, Col, Tabs,
  Divider, Space, Tag, Progress, Modal
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, FileTextOutlined,
  DownloadOutlined, PlayCircleOutlined, PauseCircleOutlined,
  FileImageOutlined, CheckCircleOutlined, Loading3QuartersOutlined,
  EditOutlined, DeleteOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { Step } = Steps;
const { Option } = Select;
const { TabPane } = Tabs;
const { TextArea } = Input;

const VoiceReplace = () => {
  // 状态管理
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [fileId, setFileId] = useState(null);
  const [fileName, setFileName] = useState('');
  const [isVideo, setIsVideo] = useState(false);
  const [transcribeTaskId, setTranscribeTaskId] = useState(null);
  const [transcribeStatus, setTranscribeStatus] = useState(null);
  const [transcription, setTranscription] = useState([]);
  const [subtitles, setSubtitles] = useState('');
  const [voiceSamples, setVoiceSamples] = useState([]);
  const [replaceTaskId, setReplaceTaskId] = useState(null);
  const [replaceStatus, setReplaceStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // 引用
  const transcribeIntervalRef = useRef(null);
  const replaceIntervalRef = useRef(null);
  const videoRef = useRef(null);
  
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
      if (transcribeIntervalRef.current) {
        clearInterval(transcribeIntervalRef.current);
      }
      if (replaceIntervalRef.current) {
        clearInterval(replaceIntervalRef.current);
      }
    };
  }, []);

  // 文件上传前检查
  const beforeUpload = (file) => {
    const isAudioVideo = file.type.startsWith('audio/') || file.type.startsWith('video/');
    if (!isAudioVideo) {
      message.error('只能上传音频或视频文件!');
      return false;
    }
    
    const isLt100M = file.size / 1024 / 1024 < 100;
    if (!isLt100M) {
      message.error('文件必须小于100MB!');
      return false;
    }
    
    // 设置是否为视频
    setIsVideo(file.type.startsWith('video/'));
    
    return true;
  };

  // 处理文件上传
  const handleFileUpload = async (info) => {
    if (info.file.status === 'uploading') {
      setLoading(true);
      return;
    }
    
    if (info.file.status === 'done') {
      setLoading(false);
      message.success(`${info.file.name} 上传成功`);
      
      // 保存文件ID和名称
      setFileId(info.file.response.file_id);
      setFileName(info.file.name);
      
    } else if (info.file.status === 'error') {
      setLoading(false);
      message.error(`${info.file.name} 上传失败`);
    }
  };

  // 开始转写
  const startTranscribe = async () => {
    if (!fileId) {
      message.error('请先上传文件');
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(`/api/replace/transcribe/${fileId}`);
      
      const task_id = response.data.file_id;
      setTranscribeTaskId(task_id);
      setTranscribeStatus({
        status: 'processing',
        progress: 0
      });
      
      // 自动进入下一步
      setCurrentStep(1);
      
      // 开始检查状态
      startTranscribeStatusCheck(task_id);
    } catch (error) {
      console.error('开始转写失败:', error);
      message.error('开始转写失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 检查转写状态
  const startTranscribeStatusCheck = (task_id) => {
    // 清除之前的检查
    if (transcribeIntervalRef.current) {
      clearInterval(transcribeIntervalRef.current);
    }
    
    // 开始定期检查
    const checkStatus = async () => {
      try {
        const response = await axios.get(`/api/replace/status/${task_id}`);
        const status = response.data;
        
        setTranscribeStatus({
          status: status.status,
          progress: status.progress * 100
        });
        
        // 如果完成，获取字幕
        if (status.status === 'completed') {
          clearInterval(transcribeIntervalRef.current);
          await fetchSubtitles(task_id);
        } else if (status.status === 'failed') {
          clearInterval(transcribeIntervalRef.current);
          message.error('转写失败: ' + (status.error || '未知错误'));
        }
      } catch (error) {
        console.error('获取转写状态失败:', error);
      }
    };
    
    // 立即检查一次
    checkStatus();
    
    // 每3秒检查一次
    transcribeIntervalRef.current = setInterval(checkStatus, 3000);
  };

  // 获取字幕
  const fetchSubtitles = async (task_id) => {
    try {
      // 获取SRT格式字幕
      const response = await axios.get(`/api/replace/subtitles/${task_id}?format=srt`);
      setSubtitles(response.data.content || '');
      
      // 解析字幕内容为段落
      const segments = parseSrtSubtitles(response.data.content || '');
      setTranscription(segments);
      
      message.success('转写完成');
    } catch (error) {
      console.error('获取字幕失败:', error);
      message.error('获取字幕失败');
    }
  };

  // 解析SRT字幕为段落
  const parseSrtSubtitles = (srtContent) => {
    if (!srtContent) return [];
    
    const segments = [];
    const lines = srtContent.split('\n');
    
    let currentSegment = null;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (!line) continue;
      
      // 如果是数字（序号）
      if (/^\d+$/.test(line)) {
        if (currentSegment) {
          segments.push(currentSegment);
        }
        currentSegment = { id: parseInt(line), time: '', text: '' };
      }
      // 如果是时间码
      else if (line.includes('-->')) {
        if (currentSegment) {
          currentSegment.time = line;
          
          // 解析开始和结束时间
          const times = line.split(' --> ');
          currentSegment.start = parseTimeCode(times[0]);
          currentSegment.end = parseTimeCode(times[1]);
        }
      }
      // 如果是文本内容
      else if (currentSegment) {
        if (currentSegment.text) {
          currentSegment.text += ' ' + line;
        } else {
          currentSegment.text = line;
        }
      }
    }
    
    // 添加最后一段
    if (currentSegment) {
      segments.push(currentSegment);
    }
    
    return segments;
  };

  // 解析时间码为秒数
  const parseTimeCode = (timeCode) => {
    const parts = timeCode.split(':');
    const seconds = parts[2].split(',');
    
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(seconds[0] + '.' + seconds[1]);
  };

  // 修改字幕内容
  const handleEditTranscription = (index, newText) => {
    const updatedTranscription = [...transcription];
    updatedTranscription[index].text = newText;
    setTranscription(updatedTranscription);
    
    // 重新生成字幕文本
    generateSubtitlesFromSegments(updatedTranscription);
  };

  // 从段落生成字幕
  const generateSubtitlesFromSegments = (segments) => {
    if (!segments || segments.length === 0) return;
    
    let srtContent = '';
    
    segments.forEach(segment => {
      srtContent += `${segment.id}\n`;
      srtContent += `${segment.time}\n`;
      srtContent += `${segment.text}\n\n`;
    });
    
    setSubtitles(srtContent);
  };

  // 处理声音替换
  const handleVoiceReplace = async (values) => {
    if (!transcribeTaskId) {
      message.error('请先完成转写');
      return;
    }
    
    if (!values.voice_id) {
      message.error('请选择声音');
      return;
    }
    
    setLoading(true);
    try {
      // 准备表单数据
      const formData = new FormData();
      formData.append('voice_id', values.voice_id);
      formData.append('speed', values.speed || 1.0);
      
      // 提交替换请求
      const response = await axios.post(`/api/replace/process/${transcribeTaskId}`, formData);
      
      const task_id = response.data.file_id;
      setReplaceTaskId(task_id);
      setReplaceStatus({
        status: 'processing',
        progress: 0
      });
      
      // 自动进入下一步
      setCurrentStep(2);
      
      // 开始检查状态
      startReplaceStatusCheck(task_id);
    } catch (error) {
      console.error('声音替换失败:', error);
      message.error('声音替换失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 检查替换状态
  const startReplaceStatusCheck = (task_id) => {
    // 清除之前的检查
    if (replaceIntervalRef.current) {
      clearInterval(replaceIntervalRef.current);
    }
    
    // 开始定期检查
    const checkStatus = async () => {
      try {
        const response = await axios.get(`/api/replace/status/${task_id}`);
        const status = response.data;
        
        setReplaceStatus({
          status: status.status,
          progress: status.progress * 100,
          output_filename: status.output_filename
        });
        
        // 如果完成或失败，停止检查
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(replaceIntervalRef.current);
          
          if (status.status === 'completed') {
            message.success('声音替换成功');
          } else {
            message.error('替换失败: ' + (status.error || '未知错误'));
          }
        }
      } catch (error) {
        console.error('获取替换状态失败:', error);
      }
    };
    
    // 立即检查一次
    checkStatus();
    
    // 每3秒检查一次
    replaceIntervalRef.current = setInterval(checkStatus, 3000);
  };

  // 下载处理后的文件
  const downloadReplacedFile = async () => {
    if (!replaceTaskId || !replaceStatus || replaceStatus.status !== 'completed') {
      message.error('没有可下载的内容');
      return;
    }
    
    try {
      const response = await axios.get(`/api/replace/download/${replaceTaskId}`, {
        responseType: 'blob'
      });
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', replaceStatus.output_filename || '替换后的文件.mp4');
      document.body.appendChild(link);
      link.click();
      
      // 清理
      link.parentNode.removeChild(link);
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
      
      message.success('下载成功');
    } catch (error) {
      console.error('下载失败:', error);
      message.error('下载失败，请重试');
    }
  };

  // 预览字幕段落
  const previewSegment = (index) => {
    setCurrentSegmentIndex(index);
    setPreviewVisible(true);
  };

  // 播放/暂停预览
  const togglePreviewPlay = () => {
    if (!videoRef.current) return;
    
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };

  // 重新开始
  const handleReset = () => {
    setCurrentStep(0);
    setFileId(null);
    setFileName('');
    setIsVideo(false);
    setTranscribeTaskId(null);
    setTranscribeStatus(null);
    setTranscription([]);
    setSubtitles('');
    setReplaceTaskId(null);
    setReplaceStatus(null);
    
    if (transcribeIntervalRef.current) {
      clearInterval(transcribeIntervalRef.current);
    }
    if (replaceIntervalRef.current) {
      clearInterval(replaceIntervalRef.current);
    }
  };

  // 渲染步骤内容
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Card title="上传媒体文件" bordered={false}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Upload
                name="file"
                action="/api/replace/upload"
                beforeUpload={beforeUpload}
                onChange={handleFileUpload}
                maxCount={1}
                showUploadList={true}
                data={{ name: 'media' }}
              >
                <Button icon={<UploadOutlined />} loading={loading}>
                  选择音频或视频文件
                </Button>
                <div style={{ marginTop: 8 }}>
                  支持常见音频(MP3, WAV)和视频(MP4, AVI)格式，大小不超过100MB
                </div>
              </Upload>
              
              {fileId && (
                <div style={{ marginTop: 24 }}>
                  <Button 
                    type="primary" 
                    onClick={startTranscribe}
                    loading={loading}
                  >
                    开始转写
                  </Button>
                </div>
              )}
            </div>
          </Card>
        );
      
      case 1:
        return (
          <Card title="转写结果" bordered={false}>
            {transcribeStatus && transcribeStatus.status === 'processing' ? (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <Spin tip="正在转写..." />
                <div style={{ marginTop: 24 }}>
                  <Progress
                    percent={Math.round(transcribeStatus.progress)}
                    status="active"
                    style={{ maxWidth: '80%', margin: '0 auto' }}
                  />
                </div>
              </div>
            ) : transcription.length > 0 ? (
              <div>
                <Tabs defaultActiveKey="segments">
                  <TabPane 
                    tab={
                      <span>
                        <FileTextOutlined />
                        分段内容
                      </span>
                    }
                    key="segments"
                  >
                    <div style={{ maxHeight: '400px', overflow: 'auto', marginBottom: 16 }}>
                      {transcription.map((segment, index) => (
                        <Card 
                          key={segment.id} 
                          size="small" 
                          style={{ marginBottom: 8 }}
                          title={
                            <Space>
                              <Tag color="blue">{`#${segment.id}`}</Tag>
                              <span>{`${formatTime(segment.start)} - ${formatTime(segment.end)}`}</span>
                            </Space>
                          }
                          extra={
                            <Space>
                              <Button 
                                type="text" 
                                icon={<PlayCircleOutlined />}
                                onClick={() => previewSegment(index)}
                              >
                                预览
                              </Button>
                              <Button 
                                type="text" 
                                icon={<EditOutlined />}
                                onClick={() => {
                                  Modal.confirm({
                                    title: '编辑文本',
                                    content: (
                                      <TextArea
                                        defaultValue={segment.text}
                                        rows={4}
                                        onChange={(e) => {
                                          handleEditTranscription(index, e.target.value);
                                        }}
                                      />
                                    ),
                                    onOk() {},
                                  });
                                }}
                              >
                                编辑
                              </Button>
                            </Space>
                          }
                        >
                          <div>{segment.text}</div>
                        </Card>
                      ))}
                    </div>
                  </TabPane>
                  <TabPane 
                    tab={
                      <span>
                        <FileTextOutlined />
                        字幕文本
                      </span>
                    }
                    key="subtitles"
                  >
                    <TextArea
                      value={subtitles}
                      onChange={(e) => setSubtitles(e.target.value)}
                      rows={12}
                      style={{ fontFamily: 'monospace' }}
                    />
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary">
                        您可以直接编辑SRT格式字幕，系统将使用编辑后的文本生成新配音。
                      </Text>
                    </div>
                  </TabPane>
                </Tabs>
                
                <Divider />
                
                <Form
                  form={form}
                  layout="vertical"
                  onFinish={handleVoiceReplace}
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="voice_id"
                        label="选择替换声音"
                        rules={[{ required: true, message: '请选择声音' }]}
                      >
                        <Select 
                          placeholder="请选择声音" 
                          loading={loading}
                        >
                          {voiceSamples.map(voice => (
                            <Option key={voice.id} value={voice.id}>
                              {voice.name} {voice.tags ? `(${voice.tags.join(', ')})` : ''}
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="speed"
                        label="语速"
                        initialValue={1.0}
                      >
                        <Slider
                          min={0.7}
                          max={1.5}
                          step={0.1}
                          marks={{
                            0.7: '慢',
                            1.0: '正常',
                            1.5: '快'
                          }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <div style={{ marginTop: 24, textAlign: 'center' }}>
                    <Space>
                      <Button onClick={handleReset}>重新开始</Button>
                      <Button 
                        type="primary" 
                        htmlType="submit"
                        icon={<AudioOutlined />}
                        loading={loading}
                      >
                        开始声音替换
                      </Button>
                    </Space>
                  </div>
                </Form>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '30px 0' }}>
                <Spin />
              </div>
            )}
          </Card>
        );
      
      case 2:
        return (
          <Card title="处理结果" bordered={false}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              {replaceStatus && replaceStatus.status === 'processing' ? (
                <div>
                  <Spin tip="正在替换声音..." />
                  <div style={{ marginTop: 24 }}>
                    <Progress
                      percent={Math.round(replaceStatus.progress)}
                      status="active"
                      style={{ maxWidth: '80%', margin: '0 auto' }}
                    />
                  </div>
                </div>
              ) : replaceStatus && replaceStatus.status === 'completed' ? (
                <div>
                  <div style={{ marginBottom: 24 }}>
                    <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                    <Title level={4} style={{ marginTop: 16 }}>声音替换成功！</Title>
                  </div>
                  
                  <div style={{ marginBottom: 24 }}>
                    <Space align="baseline">
                      {isVideo ? (
                        <FileImageOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                      ) : (
                        <AudioOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                      )}
                      <Text strong>{replaceStatus.output_filename || '处理结果文件'}</Text>
                    </Space>
                  </div>
                  
                  <Space>
                    <Button 
                      type="primary" 
                      icon={<DownloadOutlined />}
                      onClick={downloadReplacedFile}
                    >
                      下载结果
                    </Button>
                    <Button onClick={handleReset}>重新开始</Button>
                  </Space>
                </div>
              ) : replaceStatus && replaceStatus.status === 'failed' ? (
                <div>
                  <div style={{ marginBottom: 24, color: '#f5222d' }}>
                    <Title level={4}>处理失败</Title>
                    <Text type="danger">请重试或联系管理员</Text>
                  </div>
                  <Button onClick={handleReset}>重新开始</Button>
                </div>
              ) : (
                                  <div>
                  <Loading3QuartersOutlined style={{ fontSize: 24 }} />
                  <div style={{ marginTop: 8 }}>
                    <Text>准备中...</Text>
                  </div>
                </div>
              )}
            </div>
          </Card>
        );
      
      default:
        return null;
    }
  };

  // 格式化时间（秒数转为时分秒）
  const formatTime = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
  };

  return (
    <div className="voice-replace">
      <div className="page-header">
        <Title level={2}>声音置换与字幕</Title>
        <Paragraph>
          替换音视频中的声音，生成同步字幕。
          上传音频或视频文件，系统将自动转写内容，然后选择新的声音进行替换。
        </Paragraph>
      </div>

      <Card bordered={false}>
        <Steps current={currentStep} className="replace-steps">
          <Step title="上传文件" description="音频或视频" />
          <Step title="转写与编辑" description="识别文本内容" />
          <Step title="声音替换" description="生成新配音" />
        </Steps>
        
        <div className="step-content" style={{ marginTop: 32 }}>
          {renderStepContent()}
        </div>
      </Card>
      
      {/* 应用场景 */}
      <Card title="应用场景" style={{ marginTop: 16 }} bordered={false}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Card title="教学视频更新" size="small" bordered>
              <Paragraph>
                更新已有教学视频的语音讲解，改进发音、语调或替换为新教师的声音，
                无需重新拍摄视频，大大节省内容更新成本。
              </Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card title="多语言教学" size="small" bordered>
              <Paragraph>
                将教学内容转换为不同语言版本，保留原始视频的同时提供多语言讲解，
                扩大教育资源的适用范围，促进教育国际化。
              </Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card title="课程无障碍化" size="small" bordered>
              <Paragraph>
                为教学视频添加清晰的字幕，帮助听障学生学习，
                同时提供标准化的语音输出，确保教学内容的清晰传达。
              </Paragraph>
            </Card>
          </Col>
        </Row>
      </Card>
      
      {/* 使用指南 */}
      <Card title="使用指南" style={{ marginTop: 16 }} bordered={false}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Title level={4}>文件准备</Title>
            <ul>
              <li>选择清晰的音频或视频文件</li>
              <li>保证原始语音内容清晰可辨</li>
              <li>控制背景噪音和干扰声音</li>
              <li>文件时长建议在10分钟以内</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>字幕编辑</Title>
            <ul>
              <li>检查并修正转写错误</li>
              <li>调整标点符号位置</li>
              <li>分割过长的句子</li>
              <li>为专业术语提供正确拼写</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>配音优化</Title>
            <ul>
              <li>选择与内容风格匹配的声音</li>
              <li>调整语速以匹配视频节奏</li>
              <li>预览确认配音效果</li>
              <li>导出后检查音视频同步性</li>
            </ul>
          </Col>
        </Row>
      </Card>
      
      {/* 预览弹窗 */}
      <Modal
        title="片段预览"
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={700}
      >
        {currentSegmentIndex >= 0 && currentSegmentIndex < transcription.length && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Text strong>时间段：</Text> 
              <Text>{`${formatTime(transcription[currentSegmentIndex].start)} - ${formatTime(transcription[currentSegmentIndex].end)}`}</Text>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <Text strong>文本内容：</Text>
              <div style={{ padding: '8px', background: '#f5f5f5', borderRadius: '4px' }}>
                {transcription[currentSegmentIndex].text}
              </div>
            </div>
            
            <div style={{ textAlign: 'center' }}>
              <Text type="secondary">
                （实际应用中，这里会显示视频/音频预览）
              </Text>
              
              <div style={{ marginTop: 16 }}>
                <Button
                  type="primary"
                  icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={togglePreviewPlay}
                >
                  {isPlaying ? '暂停' : '播放'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default VoiceReplace;