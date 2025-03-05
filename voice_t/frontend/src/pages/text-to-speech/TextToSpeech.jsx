import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { 
  Typography, Card, Button, Input, Space, 
  message, Progress, Upload, Tabs
} from 'antd';
import { 
  UploadOutlined, AudioOutlined, 
  DownloadOutlined, PlayCircleOutlined 
} from '@ant-design/icons';

import TTSControls from './components/TTSControls';
import AudioWaveform from './components/AudioWaveform';
import { 
  fetchVoiceSamples, synthesizeSpeech, 
  getSynthesisStatus, clearSynthesisResult 
} from '../../store/actions/ttsActions';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { TabPane } = Tabs;

function TextToSpeech() {
  // 状态管理
  const dispatch = useDispatch();
  const { 
    voiceSamples,
    loading, 
    synthesizing,
    taskId,
    taskStatus,
    audioUrl
  } = useSelector(state => state.tts);
  
  // 本地状态
  const [text, setText] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('');
  const [ttsParams, setTtsParams] = useState({
    speed: 1.0,
    pitch: 0.0,
    energy: 1.0,
    emotion: 'neutral',
    pause_factor: 1.0,
    language: 'zh-CN'
  });
  
  // 加载声音样本
  useEffect(() => {
    dispatch(fetchVoiceSamples());
  }, [dispatch]);
  
  // 检查合成任务状态
  useEffect(() => {
    let interval;
    
    if (taskId && synthesizing) {
      interval = setInterval(() => {
        dispatch(getSynthesisStatus(taskId));
      }, 1000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [taskId, synthesizing, dispatch]);
  
  // 处理参数变化
  const handleParamChange = (param, value) => {
    setTtsParams(prev => ({
      ...prev,
      [param]: value
    }));
  };
  
  // 开始合成
  const handleSynthesize = () => {
    if (!text.trim()) {
      message.warning('请输入文本内容');
      return;
    }
    
    if (!selectedVoice) {
      message.warning('请选择声音');
      return;
    }
    
    dispatch(synthesizeSpeech(text, selectedVoice, ttsParams));
  };
  
  // 下载合成结果
  const handleDownload = () => {
    if (!audioUrl) return;
    
    const a = document.createElement('a');
    a.href = audioUrl;
    a.download = `tts_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };
  
  // 清除结果
  const handleClear = () => {
    dispatch(clearSynthesisResult());
    setText('');
  };
  
  return (
    <div className="text-to-speech-page">
      <div className="page-header">
        <Title level={2}>个性化语音讲解</Title>
        <Paragraph>
          基于FastSpeech2和HiFi-GAN的高质量语音合成，将文本转换为自然流畅的语音。
          支持多种参数调整，实现个性化语音效果。
        </Paragraph>
      </div>
      
      <div className="content-layout">
        {/* 文本输入区域 */}
        <Card title="文本输入" className="main-card">
          <TextArea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="请输入要合成的文本，800-2000字..."
            rows={8}
            disabled={synthesizing}
          />
          
          <div className="actions-bar">
            <Space>
              <Button
                type="primary"
                icon={<AudioOutlined />}
                onClick={handleSynthesize}
                loading={synthesizing}
                disabled={!text.trim() || !selectedVoice}
              >
                开始合成
              </Button>
              
              {audioUrl && (
                <Button
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                >
                  下载结果
                </Button>
              )}
              
              <Button onClick={handleClear}>
                清除
              </Button>
            </Space>
          </div>
          
          {/* 进度条 */}
          {taskStatus && (
            <div className="progress-container">
              <div className="progress-header">
                <span>合成进度</span>
                <span>{Math.round(taskStatus.progress * 100)}%</span>
              </div>
              <Progress percent={Math.round(taskStatus.progress * 100)} />
            </div>
          )}
          
          {/* 音频播放器 */}
          {audioUrl && (
            <div className="audio-player">
              <Title level={4}>合成结果</Title>
              <AudioWaveform audioUrl={audioUrl} />
            </div>
          )}
        </Card>
        
        {/* 参数控制面板 */}
        <Card title="语音设置" className="sidebar-card">
          <div className="voice-selector">
            <Title level={5}>选择声音</Title>
            <select
              value={selectedVoice}
              onChange={e => setSelectedVoice(e.target.value)}
              disabled={synthesizing}
              className="voice-select"
            >
              <option value="">请选择声音</option>
              {voiceSamples.map(voice => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="params-container">
            <Title level={5}>参数调整</Title>
            <TTSControls
              params={ttsParams}
              onChange={handleParamChange}
              disabled={synthesizing}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}

export default TextToSpeech;