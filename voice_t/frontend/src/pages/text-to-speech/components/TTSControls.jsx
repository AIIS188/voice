import React from 'react';

function TTSControls({ params, onChange, disabled }) {
  return (
    <div className="tts-controls">
      {/* 语速控制 */}
      <div className="control-item">
        <label>语速 ({params.speed.toFixed(1)})</label>
        <input
          type="range"
          min="0.5"
          max="2.0"
          step="0.1"
          value={params.speed}
          onChange={(e) => onChange('speed', parseFloat(e.target.value))}
          disabled={disabled}
        />
      </div>
      
      {/* 音调控制 */}
      <div className="control-item">
        <label>音调 ({params.pitch.toFixed(1)})</label>
        <input
          type="range"
          min="-1.0"
          max="1.0"
          step="0.1"
          value={params.pitch}
          onChange={(e) => onChange('pitch', parseFloat(e.target.value))}
          disabled={disabled}
        />
      </div>
      
      {/* 音量控制 */}
      <div className="control-item">
        <label>音量 ({params.energy.toFixed(1)})</label>
        <input
          type="range"
          min="0.5"
          max="2.0"
          step="0.1"
          value={params.energy}
          onChange={(e) => onChange('energy', parseFloat(e.target.value))}
          disabled={disabled}
        />
      </div>
      
      {/* 情感风格 */}
      <div className="control-item">
        <label>情感风格</label>
        <div className="emotion-selector">
          {['neutral', 'happy', 'sad', 'serious'].map(emotion => (
            <label key={emotion} className="emotion-option">
              <input
                type="radio"
                checked={params.emotion === emotion}
                onChange={() => onChange('emotion', emotion)}
                disabled={disabled}
              />
              <span>{emotionLabels[emotion]}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

const emotionLabels = {
  'neutral': '平静',
  'happy': '活力',
  'sad': '忧伤',
  'serious': '严肃'
};

export default TTSControls;