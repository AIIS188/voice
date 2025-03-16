import React, { useState, useEffect, useRef } from 'react';
import { 
  Button, 
  Space, 
  message, 
  Progress, 
  Card, 
  Tabs, 
  Radio, 
  Select, 
  Input, 
  Upload, 
  Slider,
  Typography,
  Row,
  Col,
  Switch
} from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  LoadingOutlined,
  UploadOutlined,
  DownloadOutlined,
  AudioOutlined,
  SoundOutlined,
  GlobalOutlined,
  ExperimentOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;

// 定义不同模式的操作指南
const modeInstructions = {
  sft: '1. 选择预训练音色\n2. 点击生成音频按钮',
  zero_shot: '1. 上传参考音频文件 (不超过30秒)\n2. 输入参考文本\n3. 点击生成音频按钮',
  cross_lingual: '1. 上传参考音频文件 (不超过30秒)\n2. 点击生成音频按钮',
  instruct: '1. 选择预训练音色\n2. 输入指令文本\n3. 点击生成音频按钮'
};

// 定义不同模式的标题和图标
const modeIcons = {
  sft: <SoundOutlined />,
  zero_shot: <AudioOutlined />,
  cross_lingual: <GlobalOutlined />,
  instruct: <ExperimentOutlined />
};

const modeNames = {
  sft: '预训练音色',
  zero_shot: '3s极速复刻',
  cross_lingual: '跨语种复刻',
  instruct: '自然语言控制'
};

/**
 * CosyVoice TTS组件
 * 提供多种语音合成模式：预训练音色、3s极速复刻、跨语种复刻和自然语言控制
 */
const CosyVoiceTTS = ({ 
  text, 
  onComplete 
}) => {
  // 状态管理
  const [mode, setMode] = useState('sft'); // sft, zero_shot, cross_lingual, instruct
  const [voiceId, setVoiceId] = useState('');
  const [availableVoices, setAvailableVoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [instructText, setInstructText] = useState('');
  const [promptAudio, setPromptAudio] = useState(null);
  const [speed, setSpeed] = useState(1.0);
  const [seed, setSeed] = useState(Math.floor(Math.random() * 1000000));
  const [isStreaming, setIsStreaming] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  
  // 引用
  const audioRef = useRef(null);
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioBuffersRef = useRef([]);
  const audioSourceRef = useRef(null);
  const statusIntervalRef = useRef(null);
  
  // 加载可用音色
  useEffect(() => {
    loadAvailableVoices();
  }, []);
  
  // 当组件卸载时清理资源
  useEffect(() => {
    return () => {
      cleanupWebSocket();
      cleanupAudio();
      
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, []);
  
  // 监听任务状态
  useEffect(() => {
    if (taskId && !isStreaming) {
      // 启动状态检查
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
      
      // 定时检查任务状态
      statusIntervalRef.current = setInterval(() => {
        checkTaskStatus(taskId);
      }, 1000);
      
      // 清理函数
      return () => {
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
      };
    }
  }, [taskId, isStreaming]);
  
  // 加载可用音色列表
  const loadAvailableVoices = async () => {
    try {
      const response = await axios.get('/api/cosyvoice/voices');
      setAvailableVoices(response.data);
      
      // 默认选择第一个音色
      if (response.data && response.data.length > 0) {
        setVoiceId(response.data[0]);
      }
    } catch (error) {
      console.error('获取音色列表失败:', error);
      message.error('获取音色列表失败');
    }
  };
  
  // 初始化AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  };
  
  // 生成随机种子
  const generateRandomSeed = () => {
    const newSeed = Math.floor(Math.random() * 1000000);
    setSeed(newSeed);
    return newSeed;
  };
  
  // 处理模式切换
  const handleModeChange = (newMode) => {
    setMode(newMode);
    // 清理上一个模式的状态
    setAudioUrl(null);
    setTaskId(null);
    setTaskStatus(null);
    setProgress(0);
    cleanupAudio();
  };
  
  // 标准合成（非流式）
  const handleStandardSynthesis = async () => {
    // 验证输入
    if (!validateInput()) {
      return;
    }
    
    setLoading(true);
    setTaskId(null);
    setTaskStatus(null);
    setAudioUrl(null);
    setProgress(0);
    
    try {
      // 创建合成请求参数
      const params = {
        mode: mode,
        speed: speed,
        seed: seed
      };
      
      let response;
      
      // 判断是否需要上传文件
      if (mode === 'zero_shot' || mode === 'cross_lingual') {
        if (!promptAudio) {
          message.error('请上传参考音频文件');
          setLoading(false);
          return;
        }
        
        // 创建表单数据
        const formData = new FormData();
        formData.append('text', text);
        formData.append('mode', mode);
        formData.append('speed', speed);
        
        if (voiceId) {
          formData.append('voice_id', voiceId);
        }
        
        if (promptText) {
          formData.append('prompt_text', promptText);
        }
        
        if (instructText) {
          formData.append('instruct_text', instructText);
        }
        
        // 添加参考音频文件
        if (promptAudio) {
          formData.append('prompt_audio', promptAudio);
        }
        
        // 发送请求
        response = await axios.post('/api/cosyvoice/synthesize/upload', formData);
      } else {
        // JSON请求
        const requestData = {
          text: text,
          voice_id: voiceId,
          params: params
        };
        
        // 添加可选参数
        if (promptText) {
          requestData.prompt_text = promptText;
        }
        
        if (instructText) {
          requestData.instruct_text = instructText;
        }
        
        // 发送请求
        response = await axios.post('/api/cosyvoice/synthesize', requestData);
      }
      
      // 保存任务ID
      if (response && response.data && response.data.task_id) {
        setTaskId(response.data.task_id);
      } else {
        throw new Error('无效的任务ID');
      }
      
    } catch (error) {
      console.error('合成请求失败:', error);
      message.error('语音合成请求失败，请重试');
      setLoading(false);
    }
  };
  
  // 流式合成
  const handleStreamingSynthesis = async () => {
    // 验证输入
    if (!validateInput()) {
      return;
    }
    
    // 重置状态
    setLoading(true);
    setIsStreaming(true);
    setProgress(0);
    audioBuffersRef.current = [];
    
    // 初始化音频上下文
    initAudioContext();
    
    // 创建WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/api/cosyvoice/synthesize/stream`;
    
    try {
      websocketRef.current = new WebSocket(wsUrl);
      
      // 连接建立时发送参数
      websocketRef.current.onopen = () => {
        console.log('WebSocket连接已建立');
        
        // 创建请求参数
        const requestData = {
          text: text,
          voice_id: voiceId,
          params: {
            mode: mode,
            speed: speed,
            seed: seed
          }
        };
        
        // 添加可选参数
        if (promptText) {
          requestData.prompt_text = promptText;
        }
        
        if (instructText) {
          requestData.instruct_text = instructText;
        }
        
        // 发送请求
        websocketRef.current.send(JSON.stringify(requestData));
        
        // 显示开始消息
        message.info('开始流式合成');
      };
      
      // 接收数据
      websocketRef.current.onmessage = (event) => {
        handleWebSocketMessage(event);
      };
      
      // 错误处理
      websocketRef.current.onerror = (error) => {
        console.error('WebSocket错误:', error);
        setLoading(false);
        setIsStreaming(false);
        message.error('连接失败，请重试');
      };
      
      // 连接关闭
      websocketRef.current.onclose = () => {
        console.log('WebSocket连接已关闭');
        setLoading(false);
        setIsStreaming(false);
      };
      
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setLoading(false);
      setIsStreaming(false);
      message.error('无法建立连接');
    }
  };
  
  // 处理WebSocket消息
  const handleWebSocketMessage = async (event) => {
    try {
      // 检查是否为文本消息（JSON）
      if (typeof event.data === 'string') {
        const jsonData = JSON.parse(event.data);
        
        // 处理不同类型的消息
        if (jsonData.type === 'info') {
          // 接收信息
          console.log('信息:', jsonData);
        }
        else if (jsonData.type === 'progress') {
          // 更新进度
          setProgress(prev => Math.min(95, prev + 5));
        }
        else if (jsonData.type === 'complete') {
          // 合成完成
          setProgress(100);
          setIsStreaming(false);
          setLoading(false);
          
          // 触发完成回调
          if (onComplete) {
            onComplete(jsonData.duration);
          }
          
          message.success(`合成完成，时长: ${jsonData.duration?.toFixed(1) || 0} 秒`);
        }
        else if (jsonData.type === 'error') {
          // 处理错误
          message.error(`合成错误: ${jsonData.message}`);
          setIsStreaming(false);
          setLoading(false);
        }
      }
      // 处理二进制音频数据
      else if (event.data instanceof Blob) {
        const arrayBuffer = await event.data.arrayBuffer();
        
        // 获取音频上下文
        const audioContext = initAudioContext();
        
        // 解码音频数据
        audioContext.decodeAudioData(arrayBuffer, (audioBuffer) => {
          // 存储解码后的音频
          audioBuffersRef.current.push(audioBuffer);
          
          // 如果当前未播放，开始播放
          if (!isPlaying && audioContextRef.current.state !== 'suspended') {
            playNextBuffer();
          }
        }, (error) => {
          console.error('解码音频失败:', error);
        });
      }
    } catch (error) {
      console.error('处理WebSocket消息失败:', error);
    }
  };
  
  // 播放下一个音频缓冲区
  const playNextBuffer = () => {
    if (audioBuffersRef.current.length === 0) {
      return;
    }
    
    // 获取音频上下文
    const audioContext = audioContextRef.current;
    
    // 创建音频源
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffersRef.current[0];
    source.connect(audioContext.destination);
    
    // 保存音频源引用
    audioSourceRef.current = source;
    
    // 设置播放结束回调
    source.onended = () => {
      // 移除已播放的缓冲区
      audioBuffersRef.current.shift();
      
      // 如果还有下一个缓冲区，播放它
      if (audioBuffersRef.current.length > 0) {
        playNextBuffer();
      } else {
        // 如果没有更多缓冲区但流式传输仍在进行
        if (isStreaming) {
          // 等待更多数据
          setIsPlaying(false);
        } else {
          // 流式传输已结束
          setIsPlaying(false);
        }
      }
    };
    
    // 开始播放
    source.start(0);
    setIsPlaying(true);
  };
  
  // 检查任务状态
  const checkTaskStatus = async (id) => {
    if (!id) return;
    
    try {
      const response = await axios.get(`/api/cosyvoice/status/${id}`);
      const status = response.data;
      
      setTaskStatus(status);
      setProgress(status.progress * 100);
      
      // 如果已完成，设置音频URL
      if (status.status === 'completed') {
        setAudioUrl(`/api/cosyvoice/download/${id}`);
        setLoading(false);
        
        // 清除定时器
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
        
        message.success('合成完成');
        
        // 触发完成回调
        if (onComplete) {
          onComplete(status.duration);
        }
      }
      // 如果失败，显示错误
      else if (status.status === 'failed') {
        setLoading(false);
        
        // 清除定时器
        if (statusIntervalRef.current) {
          clearInterval(statusIntervalRef.current);
        }
        
        message.error(`合成失败: ${status.error || '未知错误'}`);
      }
      
    } catch (error) {
      console.error('获取任务状态失败:', error);
    }
  };
  
  // 下载音频
  const handleDownload = () => {
    if (!audioUrl) return;
    
    const a = document.createElement('a');
    a.href = audioUrl;
    a.download = `cosyvoice_tts_${new Date().getTime()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  
  // 播放/暂停标准音频
  const toggleStandardPlayback = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };
  
  // 暂停/恢复流式播放
  const toggleStreamingPlayback = () => {
    if (!audioContextRef.current) return;
    
    if (isPlaying) {
      // 暂停播放
      audioContextRef.current.suspend();
      setIsPlaying(false);
    } else {
      // 恢复播放
      audioContextRef.current.resume();
      
      // 如果没有正在播放的音频源但有缓冲区，开始播放
      if (!audioSourceRef.current && audioBuffersRef.current.length > 0) {
        playNextBuffer();
      }
      
      setIsPlaying(true);
    }
  };
  
  // 停止流式合成
  const stopStreaming = () => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.close();
    }
    setIsStreaming(false);
    setLoading(false);
    
    // 也停止播放
    if (audioSourceRef.current) {
      audioSourceRef.current.stop();
      audioSourceRef.current = null;
    }
    
    setIsPlaying(false);
  };
  
  // 清理WebSocket
  const cleanupWebSocket = () => {
    if (websocketRef.current) {
      if (websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.close();
      }
      websocketRef.current = null;
    }
  };
  
  // 清理音频
  const cleanupAudio = () => {
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {
        // 忽略已停止的错误
      }
      audioSourceRef.current = null;
    }
    
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch (e) {
        // 忽略错误
      }
      audioContextRef.current = null;
    }
    
    audioBuffersRef.current = [];
  };
  
  // 验证输入
  const validateInput = () => {
    if (!text) {
      message.warning('请输入文本内容');
      return false;
    }
    
    switch (mode) {
      case 'sft':
        if (!voiceId) {
          message.warning('请选择预训练音色');
          return false;
        }
        break;
        
      case 'zero_shot':
        if (!promptAudio) {
          message.warning('请上传参考音频文件');
          return false;
        }
        if (!promptText) {
          message.warning('请输入参考文本');
          return false;
        }
        break;
        
      case 'cross_lingual':
        if (!promptAudio) {
          message.warning('请上传参考音频文件');
          return false;
        }
        break;
        
      case 'instruct':
        if (!voiceId) {
          message.warning('请选择预训练音色');
          return false;
        }
        if (!instructText) {
          message.warning('请输入指令文本');
          return false;
        }
        break;
        
      default:
        break;
    }
    
    return true;
  };
  
  // 处理参考音频上传
  const handlePromptAudioUpload = (info) => {
    if (info.file.status === 'done') {
      setPromptAudio(info.file.originFileObj);
      message.success(`${info.file.name} 上传成功`);
    } else if (info.file.status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };
  
  // 渲染模式特定的控制面板
  const renderModePanel = () => {
    switch (mode) {
      case 'sft':
        return (
          <div className="sft-panel">
            <Form.Item label="选择预训练音色" required={true}>
              <Select
                value={voiceId}
                onChange={setVoiceId}
                placeholder="请选择预训练音色"
                style={{ width: '100%' }}
                disabled={loading || isStreaming}
              >
                {availableVoices.map(voice => (
                  <Option key={voice} value={voice}>{voice}</Option>
                ))}
              </Select>
            </Form.Item>
          </div>
        );
        
      case 'zero_shot':
        return (
          <div className="zero-shot-panel">
            <Form.Item label="上传参考音频" required={true}>
              <Upload
                name="promptAudio"
                accept="audio/*"
                maxCount={1}
                showUploadList={true}
                beforeUpload={() => false}
                onChange={handlePromptAudioUpload}
                disabled={loading || isStreaming}
              >
                <Button icon={<UploadOutlined />} disabled={loading || isStreaming}>
                  选择音频文件
                </Button>
              </Upload>
              <div style={{ marginTop: 8, color: '#999' }}>
                提示：参考音频不超过30秒，语音清晰
              </div>
            </Form.Item>
            
            <Form.Item label="参考文本" required={true}>
              <TextArea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="请输入参考音频中说的文本内容"
                rows={3}
                disabled={loading || isStreaming}
              />
            </Form.Item>
          </div>
        );
        
      case 'cross_lingual':
        return (
          <div className="cross-lingual-panel">
            <Form.Item label="上传参考音频" required={true}>
              <Upload
                name="promptAudio"
                accept="audio/*"
                maxCount={1}
                showUploadList={true}
                beforeUpload={() => false}
                onChange={handlePromptAudioUpload}
                disabled={loading || isStreaming}
              >
                <Button icon={<UploadOutlined />} disabled={loading || isStreaming}>
                  选择音频文件
                </Button>
              </Upload>
              <div style={{ marginTop: 8, color: '#999' }}>
                提示：参考音频不超过30秒，语音清晰
              </div>
            </Form.Item>
            
            <Alert
              message="跨语种复刻提示"
              description="合成文本的语言应与参考音频的语言不同，例如：参考音频为中文，合成文本为英文。"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
          </div>
        );
        
      case 'instruct':
        return (
          <div className="instruct-panel">
            <Form.Item label="选择预训练音色" required={true}>
              <Select
                value={voiceId}
                onChange={setVoiceId}
                placeholder="请选择预训练音色"
                style={{ width: '100%' }}
                disabled={loading || isStreaming}
              >
                {availableVoices.map(voice => (
                  <Option key={voice} value={voice}>{voice}</Option>
                ))}
              </Select>
            </Form.Item>
            
            <Form.Item label="指令文本" required={true}>
              <TextArea
                value={instructText}
                onChange={(e) => setInstructText(e.target.value)}
                placeholder="请输入指令文本，例如：请用悲伤的语气朗读"
                rows={3}
                disabled={loading || isStreaming}
              />
            </Form.Item>
          </div>
        );
        
      default:
        return null;
    }
  };
  
  // 渲染音频播放控制
  const renderAudioControl = () => {
    if (isStreaming) {
      // 流式合成播放控制
      return (
        <Button
          icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={toggleStreamingPlayback}
          disabled={audioBuffersRef.current.length === 0}
        >
          {isPlaying ? '暂停' : '播放'}
        </Button>
      );
    } else if (audioUrl) {
      // 标准合成播放控制
      return (
        <div className="audio-control">
          <audio
            ref={audioRef}
            src={audioUrl}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => setIsPlaying(false)}
            style={{ display: 'none' }}
          />
          
          <Space>
            <Button
              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
              onClick={toggleStandardPlayback}
            >
              {isPlaying ? '暂停' : '播放'}
            </Button>
            
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
            >
              下载
            </Button>
          </Space>
        </div>
      );
    }
    
    return null;
  };
  
  return (
    <div className="cosyvoice-tts">
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {modeIcons[mode]} <span style={{ marginLeft: 8 }}>CosyVoice语音合成 - {modeNames[mode]}</span>
          </div>
        }
        bordered={false}
      >
        <Tabs activeKey={mode} onChange={handleModeChange}>
          <TabPane 
            tab={
              <span>
                <SoundOutlined /> 预训练音色
              </span>
            } 
            key="sft"
          />
          <TabPane 
            tab={
              <span>
                <AudioOutlined /> 3s极速复刻
              </span>
            } 
            key="zero_shot"
          />
          <TabPane 
            tab={
              <span>
                <GlobalOutlined /> 跨语种复刻
              </span>
            } 
            key="cross_lingual"
          />
          <TabPane 
            tab={
              <span>
                <ExperimentOutlined /> 自然语言控制
              </span>
            } 
            key="instruct"
          />
        </Tabs>
        
        <div className="instruction-panel" style={{ marginBottom: 16, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
          <Title level={5}>操作步骤</Title>
          <Text>
            {modeInstructions[mode].split('\n').map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </Text>
        </div>
        
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Form layout="vertical">
              {renderModePanel()}
              
              <Form.Item label="合成参数">
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="语速" required={false}>
                      <Slider
                        min={0.5}
                        max={2.0}
                        step={0.1}
                        value={speed}
                        onChange={setSpeed}
                        disabled={loading || isStreaming}
                        marks={{
                          0.5: '慢',
                          1.0: '标准',
                          2.0: '快'
                        }}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="随机种子"></Form.Item>