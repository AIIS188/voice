import React, { useEffect, useRef, useState } from 'react';

function AudioWaveform({ audioUrl }) {
  const canvasRef = useRef(null);
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // 波形绘制逻辑
  useEffect(() => {
    if (!canvasRef.current || !audioUrl) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // 绘制静态波形函数
    const drawStaticWaveform = () => {
      // 波形绘制代码...
    };
    
    // 绘制动态波形函数
    const drawDynamicWaveform = () => {
      // 动态波形绘制代码...
    };
    
    if (isPlaying) {
      const animationId = requestAnimationFrame(drawDynamicWaveform);
      return () => cancelAnimationFrame(animationId);
    } else {
      drawStaticWaveform();
    }
  }, [audioUrl, isPlaying]);
  
  // 播放/暂停控制
  const togglePlayback = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };
  
  // 监听音频播放结束
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    
    const handleEnded = () => setIsPlaying(false);
    audio.addEventListener('ended', handleEnded);
    
    return () => {
      audio.removeEventListener('ended', handleEnded);
    };
  }, []);
  
  return (
    <div className="audio-waveform">
      <canvas 
        ref={canvasRef} 
        width="600" 
        height="100"
        className="waveform-canvas"
      />
      
      <div className="playback-controls">
        <button
          onClick={togglePlayback}
          className={`playback-button ${isPlaying ? 'playing' : ''}`}
        >
          {isPlaying ? '暂停' : '播放'}
        </button>
        
        <audio 
          ref={audioRef}
          src={audioUrl} 
          className="hidden-audio"
        />
      </div>
    </div>
  );
}

export default AudioWaveform;