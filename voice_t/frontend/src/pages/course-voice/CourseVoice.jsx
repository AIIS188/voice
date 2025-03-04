import React, { useState, useEffect, useRef } from 'react';
import { 
  Typography, Card, Form, Input, Button, Select, 
  Slider, Upload, message, Steps, List, Spin,
  Row, Col, Divider, Progress, Space, Tag
} from 'antd';
import { 
  UploadOutlined, FileTextOutlined, SoundOutlined,
  DownloadOutlined, CheckCircleOutlined, LoadingOutlined,
  PlayCircleOutlined, EditOutlined, FileOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;
const { Option } = Select;
const { Step } = Steps;

const CourseVoice = () => {
  // 状态管理
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [fileId, setFileId] = useState(null);
  const [fileName, setFileName] = useState('');
  const [extractedText, setExtractedText] = useState([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState('');
  const [voiceSamples, setVoiceSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [textLoading, setTextLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  
  // 引用
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
    };
  }, []);

  // 课件文件上传前检查
  const beforeUpload = (file) => {
    const isPPT = file.type === 'application/vnd.ms-powerpoint' || 
                  file.type === 'application/vnd.openxmlformats-officedocument.presentationml.presentation' ||
                  file.name.endsWith('.ppt') ||
                  file.name.endsWith('.pptx');
    
    if (!isPPT) {
      message.error('只能上传PPT/PPTX文件!');
      return false;
    }
    
    const isLt20M = file.size / 1024 / 1024 < 20;
    if (!isLt20M) {
      message.error('文件必须小于20MB!');
      return false;
    }
    
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
      
      // 提取文本
      extractText(info.file.response.file_id);
    } else if (info.file.status === 'error') {
      setLoading(false);
      message.error(`${info.file.name} 上传失败`);
    }
  };

  // 提取课件文本
  const extractText = async (id) => {
    setTextLoading(true);
    try {
      const response = await axios.get(`/api/course/extract/${id}`);
      setExtractedText(response.data.extracted_text || []);
      
      // 自动进入下一步
      setCurrentStep(1);
    } catch (error) {
      console.error('提取文本失败:', error);
      message.error('提取文本失败，请重试');
    } finally {
      setTextLoading(false);
    }
  };

  // 修改提取文本（示例函数，实际项目中需要实现文本编辑功能）
  const handleEditText = (slide_id) => {
    message.info(`编辑第${slide_id}页文本（此功能演示中）`);
  };

  // 生成有声课件
  const generateVoicedCourseware = async (values) => {
    if (!fileId) {
      message.error('请先上传课件');
      return;
    }
    
    if (!selectedVoiceId) {
      message.error('请选择声音');
      return;
    }
    
    setLoading(true);
    try {
      // 准备表单数据
      const formData = new FormData();
      formData.append('voice_id', selectedVoiceId);
      formData.append('speed', values.speed || 1.0);
      
      // 提交生成请求
      const response = await axios.post(`/api/course/synthesize/${fileId}`, formData);
      
      const task_id = response.data.file_id;
      setTaskId(task_id);
      setTaskStatus({
        status: 'processing',
        progress: 0,
        slides_processed: 0,
        total_slides: extractedText.length
      });
      
      // 自动进入下一步
      setCurrentStep(2);
      
      // 轮询检查任务状态
      startStatusCheck(task_id);
    } catch (error) {
      console.error('生成有声课件失败:', error);
      message.error('生成有声课件失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 开始状态检查
  const startStatusCheck = (task_id) => {
    // 清除之前的检查
    if (statusCheckIntervalRef.current) {
      clearInterval(statusCheckIntervalRef.current);
    }
    
    // 开始定期检查
    const checkStatus = async () => {
      try {
        const response = await axios.get(`/api/course/status/${task_id}`);
        const status = response.data;
        
        setTaskStatus({
          status: status.status,
          progress: status.progress * 100,
          slides_processed: status.slides_processed,
          total_slides: status.total_slides,
          output_filename: status.output_filename
        });
        
        // 如果完成或失败，停止检查
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(statusCheckIntervalRef.current);
          
          if (status.status === 'completed') {
            message.success('有声课件生成成功');
          } else {
            message.error('生成失败: ' + (status.error || '未知错误'));
          }
        }
      } catch (error) {
        console.error('获取任务状态失败:', error);
      }
    };
    
    // 立即检查一次
    checkStatus();
    
    // 每3秒检查一次
    statusCheckIntervalRef.current = setInterval(checkStatus, 3000);
  };

  // 下载有声课件
  const downloadVoicedCourseware = async () => {
    if (!taskId || !taskStatus || taskStatus.status !== 'completed') {
      message.error('没有可下载的内容');
      return;
    }
    
    try {
      const response = await axios.get(`/api/course/download/${taskId}`, {
        responseType: 'blob'
      });
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', taskStatus.output_filename || '有声课件.pptx');
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

  // 重新开始
  const handleReset = () => {
    setCurrentStep(0);
    setFileId(null);
    setFileName('');
    setExtractedText([]);
    setSelectedVoiceId('');
    setTaskId(null);
    setTaskStatus(null);
    
    if (statusCheckIntervalRef.current) {
      clearInterval(statusCheckIntervalRef.current);
    }
  };

  // 渲染步骤内容
  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Card title="上传课件" bordered={false}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Upload
                name="file"
                action="/api/course/upload"
                beforeUpload={beforeUpload}
                onChange={handleFileUpload}
                maxCount={1}
                showUploadList={true}
                data={{ name: 'course' }}
              >
                <Button icon={<UploadOutlined />} loading={loading}>
                  选择课件文件
                </Button>
                <div style={{ marginTop: 8 }}>
                  支持PPT, PPTX格式，大小不超过20MB
                </div>
              </Upload>
            </div>
          </Card>
        );
      
      case 1:
        return (
          <Card title="课件文本" bordered={false}>
            <div style={{ marginBottom: 16 }}>
              <Space align="center">
                <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                <span>{fileName}</span>
                <Tag color="blue">{`${extractedText.length} 页`}</Tag>
              </Space>
            </div>

            <Form
              form={form}
              layout="vertical"
              onFinish={generateVoicedCourseware}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="voice_id"
                    label="选择声音"
                    rules={[{ required: true, message: '请选择声音' }]}
                  >
                    <Select 
                      placeholder="请选择声音" 
                      onChange={(value) => setSelectedVoiceId(value)}
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
              
              <Divider orientation="left">提取的文本内容</Divider>
              
              <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                <List
                  loading={textLoading}
                  itemLayout="horizontal"
                  dataSource={extractedText}
                  renderItem={item => (
                    <List.Item
                      actions={[
                        <Button 
                          type="link" 
                          icon={<EditOutlined />}
                          onClick={() => handleEditText(item.slide_id)}
                        >
                          编辑
                        </Button>
                      ]}
                    >
                      <List.Item.Meta
                        avatar={<Tag color="blue">{`第 ${item.slide_id} 页`}</Tag>}
                        title={item.title || `幻灯片 ${item.slide_id}`}
                        description={
                          <div>
                            <Text ellipsis={{ rows: 2 }}>{item.content}</Text>
                            {item.notes && (
                              <div style={{ marginTop: 8 }}>
                                <Text type="secondary" italic>{`备注: ${item.notes}`}</Text>
                              </div>
                            )}
                          </div>
                        }
                      />
                    </List.Item>
                  )}
                />
              </div>
              
              <div style={{ marginTop: 24, textAlign: 'center' }}>
                <Space>
                  <Button onClick={handleReset}>重新上传</Button>
                  <Button 
                    type="primary" 
                    htmlType="submit"
                    icon={<SoundOutlined />}
                    loading={loading}
                  >
                    生成有声课件
                  </Button>
                </Space>
              </div>
            </Form>
          </Card>
        );
      
      case 2:
        return (
          <Card title="生成结果" bordered={false}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              {taskStatus && taskStatus.status === 'processing' ? (
                <div>
                  <Spin tip="正在生成有声课件..." />
                  <div style={{ marginTop: 24 }}>
                    <Progress
                      percent={Math.round(taskStatus.progress)}
                      status="active"
                      style={{ maxWidth: '80%', margin: '0 auto' }}
                    />
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary">
                        {`处理进度: ${taskStatus.slides_processed || 0}/${taskStatus.total_slides || extractedText.length} 页`}
                      </Text>
                    </div>
                  </div>
                </div>
              ) : taskStatus && taskStatus.status === 'completed' ? (
                <div>
                  <div style={{ marginBottom: 24 }}>
                    <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                    <Title level={4} style={{ marginTop: 16 }}>有声课件生成成功！</Title>
                  </div>
                  
                  <div style={{ marginBottom: 24 }}>
                    <Space align="baseline">
                      <FileOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                      <Text strong>{taskStatus.output_filename || '有声课件.pptx'}</Text>
                    </Space>
                  </div>
                  
                  <Space>
                    <Button 
                      type="primary" 
                      icon={<DownloadOutlined />}
                      onClick={downloadVoicedCourseware}
                    >
                      下载有声课件
                    </Button>
                    <Button onClick={handleReset}>重新开始</Button>
                  </Space>
                </div>
              ) : taskStatus && taskStatus.status === 'failed' ? (
                <div>
                  <div style={{ marginBottom: 24, color: '#f5222d' }}>
                    <Title level={4}>生成失败</Title>
                    <Text type="danger">请重试或联系管理员</Text>
                  </div>
                  <Button onClick={handleReset}>重新开始</Button>
                </div>
              ) : (
                <div>
                  <LoadingOutlined style={{ fontSize: 24 }} />
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

  return (
    <div className="course-voice">
      <div className="page-header">
        <Title level={2}>课件语音化</Title>
        <Paragraph>
          上传PPT等课件，提取文本并生成配音，制作有声课件。
          支持自动提取文本、选择声音样本和调整语音参数，方便教师快速制作教学资料。
        </Paragraph>
      </div>

      <Card bordered={false}>
        <Steps current={currentStep} className="course-steps">
          <Step title="上传课件" description="选择PPT文件" />
          <Step title="提取文本" description="确认和编辑文本" />
          <Step title="生成有声课件" description="下载结果" />
        </Steps>
        
        <div className="step-content" style={{ marginTop: 32 }}>
          {renderStepContent()}
        </div>
      </Card>
      
      {/* 使用指南 */}
      <Card title="使用指南" style={{ marginTop: 16 }} bordered={false}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Title level={4}>课件准备</Title>
            <ul>
              <li>尽量使用规范格式的PPT</li>
              <li>确保幻灯片中文本清晰可见</li>
              <li>使用幻灯片备注添加讲解内容</li>
              <li>控制每页内容不要过多</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>效果优化</Title>
            <ul>
              <li>选择与内容匹配的声音</li>
              <li>检查并编辑提取的文本</li>
              <li>调整语速以匹配课件节奏</li>
              <li>添加必要的停顿和重音</li>
            </ul>
          </Col>
          <Col xs={24} md={8}>
            <Title level={4}>使用技巧</Title>
            <ul>
              <li>通过编辑文本添加过渡提示</li>
              <li>为专业术语提供正确读音</li>
              <li>保存常用声音和设置</li>
              <li>分享制作好的有声课件</li>
            </ul>
          </Col>
        </Row>
      </Card>
      
      {/* 应用场景 */}
      <Card title="应用场景" style={{ marginTop: 16 }} bordered={false}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} lg={8}>
            <Card title="远程教学" size="small" bordered>
              <Paragraph>
                为远程学习学生提供带有标准语音讲解的课件，提高自学效果。
                学生可以根据自己的节奏反复学习，理解知识点。
              </Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={12} lg={8}>
            <Card title="预习复习材料" size="small" bordered>
              <Paragraph>
                制作用于课前预习和课后复习的有声教学材料，
                帮助学生巩固课堂知识，提高学习效率。
              </Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={12} lg={8}>
            <Card title="特殊教育支持" size="small" bordered>
              <Paragraph>
                为有阅读障碍或视力障碍的学生提供有声课件，
                确保他们能够平等获取教育资源和内容。
              </Paragraph>
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

export default CourseVoice;