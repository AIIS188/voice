import React from 'react';
import { Slider, Radio, Space, Typography } from 'antd';

const { Text } = Typography;

function TTSControls({ params, onChange, disabled }) {
  // 情感风格标签
  const emotionLabels = {
    'neutral': '平静',
    'happy': '活力',
    'sad': '忧伤',
    'serious': '严肃'
  };

  return (
    <div className="tts-controls">
      {/* 语速控制 */}
      <div className="control-item" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text>语速</Text>
          <Text>{params.speed.toFixed(1)}</Text>
        </div>
        <Slider
          min={0.5}
          max={2.0}
          step={0.1}
          value={params.speed}
          onChange={(value) => onChange('speed', value)}
          disabled={disabled}
          marks={{
            0.5: '慢',
            1.0: '正常',
            2.0: '快'
          }}
        />
      </div>
      
      {/* 音调控制 */}
      <div className="control-item" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text>音调</Text>
          <Text>{params.pitch.toFixed(1)}</Text>
        </div>
        <Slider
          min={-1.0}
          max={1.0}
          step={0.1}
          value={params.pitch}
          onChange={(value) => onChange('pitch', value)}
          disabled={disabled}
          marks={{
            '-1.0': '低',
            '0': '正常',
            '1.0': '高'
          }}
        />
      </div>
      
      {/* 音量控制 */}
      <div className="control-item" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text>音量</Text>
          <Text>{params.energy.toFixed(1)}</Text>
        </div>
        <Slider
          min={0.5}
          max={2.0}
          step={0.1}
          value={params.energy}
          onChange={(value) => onChange('energy', value)}
          disabled={disabled}
          marks={{
            0.5: '低',
            1.0: '正常',
            2.0: '高'
          }}
        />
      </div>
      
      {/* 情感风格 */}
      <div className="control-item" style={{ marginBottom: 16 }}>
        <Text>情感风格</Text>
        <div className="emotion-selector" style={{ marginTop: 8 }}>
          <Radio.Group 
            value={params.emotion}
            onChange={(e) => onChange('emotion', e.target.value)}
            disabled={disabled}
          >
            <Space direction="vertical">
              {Object.entries(emotionLabels).map(([key, label]) => (
                <Radio key={key} value={key}>{label}</Radio>
              ))}
            </Space>
          </Radio.Group>
        </div>
      </div>
    </div>
  );
}

export default TTSControls;