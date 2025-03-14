import React, { useState, useEffect } from 'react';
import { 
  Typography, Card, Button, Input, Select, 
  Tabs, Space, Radio, Slider, message, Spin 
} from 'antd';
import { 
  AudioOutlined, DownloadOutlined, 
  CloudOutlined, PlayCircleOutlined,
  SwapOutlined
} from '@ant-design/icons';
import axios from 'axios';

// 导入流式TTS组件
import StreamingTTS from '../../components/StreamingTTS';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

const TextToSpeech = () => {
  // 状态管理
  const [text, setText] = useState('');
  const [voiceSamples, setVoiceSamples] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [loading, setLoading] = useState(false);
  const [synthesisMode, setSynthesisMode] = useState('streaming'); // 'streaming' or 'standard'
  
  // 语音合成参数
  const [ttsParams, setTtsParams] = useState({
    speed: 1.0,
    pitch: 0.0,
    energy: 1.0,
    emotion: 'neutral',
    pause_factor: 1.0,
    language: 'zh-CN'
  });
  
  // 标准合成相关状态
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  
  // 加载声音样本
  useEffect(() => {
    loadVoiceSamples();
  }, []);
  
  // 当有任务ID时，定期检查状态
  useEffect(() => {
    let interval;
    
    if (taskId && !taskStatus?.status !== 'completed' && !taskStatus?.status !== 'failed') {
      interval = setInterval(() => {
        checkTaskStatus(taskId);
      }, 1000);
    }
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [taskId, taskStatus]);
  
  // 加载声音样本
  const loadVoiceSamples = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/voice/list');
      
      // 添加预设声音样本
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
      
      // 合并预设与实际声音样本
      const allVoices = [...presetVoices];
      
      if (response?.data?.items?.length) {
        // 只添加状态为ready的声音样本
        const readyVoices = response.data.items.filter(v => v.status === 'ready');
        allVoices.push(...readyVoices);
      }
      
      setVoiceSamples(allVoices);
    } catch (error) {
      console.error('获取声音样本失败:', error);
      message.error('获取声音样本失败，仅显示预设声音');
      
      // 使用预设声音作为后备
      setVoiceSamples([
        {
          id: 'preset_1',
          name: '男声教师1',
          tags: ['male', 'teacher']
        },
        {
          id: 'preset_2',
          name: '女声教师1',
          tags: ['female', 'teacher']
        }
      ]);
    } finally {
      setLoading(false);
    }
  };
  
  // 处理参数变更
  const handleParamChange = (param, value) => {
    setTtsParams(prev => ({
      ...prev,
      [param]: value
    }));
  };
  
  // 标准合成
  const handleStandardSynthesis = async () => {
    if (!validateInput()) return;
    
    setLoading(true);
    try {
      // 发送合成请求
      const response = await axios.post('/api/tts/synthesize', {
        text,
        voice_id: selectedVoice,
        params: ttsParams
      });
      
      // 保存任务ID
      setTaskId(response.data.task_id);
      setTaskStatus({ status: 'pending', progress: 0 });
      
      // 开始检查状态
      checkTaskStatus(response.data.task_id);
      
    } catch (error) {
      console.error('合成请求失败:', error);
      message.error('语音合成请求失败，请重试');
    } finally {
      setLoading(false);
    }
  };
  
  // 检查任务状态
  const checkTaskStatus = async (id) => {
    if (!id || checkingStatus) return;
    
    setCheckingStatus(true);
    try {
      const response = await axios.get(`/api/tts/status/${id}`);
      setTaskStatus(response.data);
      
      // 如果已完成，设置音频URL
      if (response.data.status === 'completed') {
        setAudioUrl(`/api/tts/download/${id}`);
      }
      
    } catch (error) {
      console.error('获取任务状态失败:', error);
    } finally {
      setCheckingStatus(false);
    }
  };
  
  // 下载音频
  const handleDownload = () => {
    if (!audioUrl) return;
    
    const a = document.createElement('a');
    a.href = audioUrl;
    a.download = `tts_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  
  // 预览语音
  const handlePreview = async () => {
    if (!validateInput()) return;
    
    setLoading(true);
    try {
      // 使用前200个字符作为预览
      const previewText = text.slice(0, 200);
      
      // 发送预览请求
      const response = await axios.post('/api/tts/preview', {
        text: previewText,
        voice_id: selectedVoice,
        params: ttsParams
      });
      
      // 保存任务ID
      setTaskId(response.data.task_id);
      setTaskStatus({ status: 'pending', progress: 0 });
      
      // 开始检查状态
      checkTaskStatus(response.data.task_id);
      
    } catch (error) {
      console.error('预览请求失败:', error);
      message.error('语音预览请求失败，请重试');
    } finally {
      setLoading(false);
    }
  };
  
  // 验证输入
  const validateInput = () => {
    if (!text.trim()) {
      message.warning('请输入文本内容');
      return false;
    }
    
    if (!selectedVoice) {
      message.warning('请选择声音');
      return false;
    }
    
    return true;
  };
  
  // 切换合成模式
  const toggleSynthesisMode = () => {
    setSynthesisMode(prev => prev === 'streaming' ? 'standard' : 'streaming');
    // 重置相关状态
    setTaskId(null);
    setTaskStatus(null);
    setAudioUrl(null);
  };
  
  // 渲染合成控制按钮
  const renderSynthesisControls = () => {
    if (synthesisMode === 'streaming') {
      // 流式合成控制
      return (
        <StreamingTTS 
          text={text}
          voiceId={selectedVoice}
          params={ttsParams}
          onStart={() => message.info('开始流式合成')}
          onComplete={(duration) => message.success(`合成完成，时长: ${duration?.toFixed(1) || 0} 秒`)}
          onError={(error) => message.error(`合成失败: ${error.message}`)}
        />
      );
    } else {
      // 标准合成控制
      return (
        <Space>
          <Button
            type="primary"
            icon={<AudioOutlined />}
            onClick={handleStandardSynthesis}
            loading={loading || (taskStatus && taskStatus.status === 'processing')}
            disabled={!text.trim() || !selectedVoice}
          >
            开始合成
          </Button>
          
          <Button
            icon={<PlayCircleOutlined />}
            onClick={handlePreview}
            disabled={!text.trim() || !selectedVoice || loading}
          >
            预览
          </Button>
          
          {audioUrl && (
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
            >
              下载结果
            </Button>
          )}
        </Space>
      );
    }
  };
  
  // 渲染任务状态
  const renderTaskStatus = () => {
    if (!taskStatus) return null;
    
    let statusText = '';
    switch (taskStatus.status) {
      case 'pending':
        statusText = '等待处理...';
        break;
      case 'processing':
        statusText = `处理中... ${Math.round(taskStatus.progress * 100)}%`;
        break;
      case 'completed':
        statusText = '合成完成';
        break;
      case 'failed':
        statusText = `合成失败: ${taskStatus.error || '未知错误'}`;
        break;
      default:
        statusText = taskStatus.status;
    }
    
    return (
      <div className="task-status">
        {taskStatus.status === 'processing' && (
          <Spin spinning={true} />
        )}
        <span style={{ marginLeft: 8 }}>{statusText}</span>
      </div>
    );
  };
  
  // 渲染音频播放器
  const renderAudioPlayer = () => {
    if (!audioUrl) return null;
    
    return (
      <div className="audio-player" style={{ marginTop: 16 }}>
        <audio controls src={audioUrl} style={{ width: '100%' }} />
      </div>
    );
  };
  
  return (
    <div className="text-to-speech-page">
      <div className="page-header">
        <Title level={2}>个性化语音讲解</Title>
        <Paragraph>
          基于PaddleSpeech的高质量语音合成，将文本转换为自然流畅的语音。
          支持流式合成和多种参数调整，实现个性化语音效果。
        </Paragraph>
      </div>
      
      <div className="synthesis-mode-toggle" style={{ marginBottom: 16 }}>
        <Button 
          icon={<SwapOutlined />} 
          onClick={toggleSynthesisMode}
        >
          切换到{synthesisMode === 'streaming' ? '标准' : '流式'}合成
        </Button>
        <Text type="secondary" style={{ marginLeft: 8 }}>
          当前模式: {synthesisMode === 'streaming' ? '流式合成 (实时播放)' : '标准合成 (完整下载)'}
        </Text>
      </div>
      
      <div className="content-layout">
        <Card title="文本输入">
          <TextArea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="请输入要合成的文本，支持800-2000字..."
            rows={8}
            disabled={loading || (taskStatus && taskStatus.status === 'processing')}
          />
          
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 16 }}>
              <label>选择声音：</label>
              <Select
                style={{ width: 250, marginLeft: 8 }}
                value={selectedVoice}
                onChange={setSelectedVoice}
                loading={loading}
                disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                placeholder="请选择声音"
              >
                {voiceSamples.map(voice => (
                  <Option key={voice.id} value={voice.id}>
                    {voice.name} {voice.tags ? `(${voice.tags.join(', ')})` : ''}
                  </Option>
                ))}
              </Select>
            </div>
            
            <div className="controls-container" style={{ marginTop: 16 }}>
              {renderSynthesisControls()}
            </div>
            
            {synthesisMode === 'standard' && (
              <>
                {renderTaskStatus()}
                {renderAudioPlayer()}
              </>
            )}
          </div>
        </Card>
        
        <Card title="语音参数调整" style={{ marginTop: 16 }}>
          <Tabs defaultActiveKey="basic">
            <TabPane tab="基本参数" key="basic">
              <div className="param-item">
                <div className="param-label">语速</div>
                <Slider
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={ttsParams.speed}
                  onChange={val => handleParamChange('speed', val)}
                  disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                  marks={{
                    0.5: '慢',
                    1.0: '标准',
                    2.0: '快'
                  }}
                />
              </div>
              
              <div className="param-item">
                <div className="param-label">音调</div>
                <Slider
                  min={-1.0}
                  max={1.0}
                  step={0.1}
                  value={ttsParams.pitch}
                  onChange={val => handleParamChange('pitch', val)}
                  disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                  marks={{
                    '-1.0': '低',
                    '0': '标准',
                    '1.0': '高'
                  }}
                />
              </div>
              
              <div className="param-item">
                <div className="param-label">音量</div>
                <Slider
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={ttsParams.energy}
                  onChange={val => handleParamChange('energy', val)}
                  disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                  marks={{
                    0.5: '轻',
                    1.0: '标准',
                    2.0: '响'
                  }}
                />
              </div>
            </TabPane>
            
            <TabPane tab="情感风格" key="emotion">
              <div className="param-item">
                <div className="param-label">情感</div>
                <Radio.Group
                  value={ttsParams.emotion}
                  onChange={e => handleParamChange('emotion', e.target.value)}
                  disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                >
                  <Radio.Button value="neutral">平静</Radio.Button>
                  <Radio.Button value="happy">活力</Radio.Button>
                  <Radio.Button value="sad">忧伤</Radio.Button>
                  <Radio.Button value="serious">严肃</Radio.Button>
                </Radio.Group>
              </div>
              
              <div className="param-item">
                <div className="param-label">停顿长度</div>
                <Slider
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={ttsParams.pause_factor}
                  onChange={val => handleParamChange('pause_factor', val)}
                  disabled={loading || (taskStatus && taskStatus.status === 'processing')}
                  marks={{
                    0.5: '短',
                    1.0: '标准',
                    2.0: '长'
                  }}
                />
              </div>
            </TabPane>
          </Tabs>
        </Card>
      </div>
    </div>
  );
};

export default TextToSpeech;