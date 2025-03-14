import React, { useEffect, useRef, useState } from 'react';
import { Button, Space } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';

function AudioWaveform({ audioUrl }) {
  const audioRef = useRef(null);
  const canvasRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const animationRef = useRef(null);
  
  // 初始化
  useEffect(() => {
    if (!audioUrl) return;
    
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    
    // 加载音频元数据
    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration);
    });
    
    // 播放结束处理
    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setCurrentTime(0);
      cancelAnimationFrame(animationRef.current);
    });
    
    return () => {
      audio.pause();
      audio.src = '';
      cancelAnimationFrame(animationRef.current);
    };
  }, [audioUrl]);
  
  // 绘制波形
  useEffect(() => {
    if (!canvasRef.current || !audioUrl) return;
    
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    
    // 清除画布
    context.clearRect(0, 0, canvas.width, canvas.height);
    
    // 设置波形样式
    context.fillStyle = '#1890ff';
    context.strokeStyle = '#1890ff';
    context.lineWidth = 2;
    
    // 绘制静态波形 (简化版)
    const drawStaticWaveform = () => {
      const width = canvas.width;
      const height = canvas.height;
      const bars = 50;
      const barWidth = width / bars;
      
      context.beginPath();
      
      for (let i = 0; i < bars; i++) {
        // 生成随机高度 (实际应该读取音频数据)
        const amplitude = Math.random() * 0.5 + 0.2;
        const barHeight = height * amplitude;
        
        const x = i * barWidth;
        const y = (height - barHeight) / 2;
        
        context.rect(x, y, barWidth - 2, barHeight);
      }
      
      context.fill();
    };
    
    drawStaticWaveform();
    
    // 绘制播放进度
    const drawProgress = () => {
      if (!audioRef.current || duration === 0) return;
      
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      
      const progress = currentTime / duration;
      const progressX = canvas.width * progress;
      
      // 清除之前的进度线
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // 重绘波形
      drawStaticWaveform();
      
      // 绘制已播放部分的颜色覆盖
      ctx.fillStyle = 'rgba(24, 144, 255, 0.4)';
      ctx.fillRect(0, 0, progressX, canvas.height);
      
      // 绘制进度线
      ctx.beginPath();
      ctx.strokeStyle = '#f5222d';
      ctx.lineWidth = 2;
      ctx.moveTo(progressX, 0);
      ctx.lineTo(progressX, canvas.height);
      ctx.stroke();
    };
    
    // 动画更新
    const updateProgress = () => {
      if (audioRef.current) {
        setCurrentTime(audioRef.current.currentTime);
      }
      
      drawProgress();
      animationRef.current = requestAnimationFrame(updateProgress);
    };
    
    if (isPlaying) {
      updateProgress();
    } else {
      drawProgress();
    }
    
    return () => {
      cancelAnimationFrame(animationRef.current);
    };
  }, [audioUrl, isPlaying, currentTime, duration]);
  
  // 播放/暂停控制
  const togglePlayback = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
      cancelAnimationFrame(animationRef.current);
    } else {
      audioRef.current.play();
    }
    
    setIsPlaying(!isPlaying);
  };
  
  // 格式化时间
  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  
  if (!audioUrl) return null;
  
  return (
    <div className="audio-waveform" style={{ marginTop: 16 }}>
      <canvas 
        ref={canvasRef} 
        width={600} 
        height={80}
        style={{ width: '100%', height: 80, backgroundColor: '#f5f5f5', borderRadius: 4 }}
      />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        <span>{formatTime(currentTime)}</span>
        <span>{formatTime(duration)}</span>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
        <Button 
          type="primary" 
          shape="circle" 
          size="large"
          icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />} 
          onClick={togglePlayback}
        />
      </div>
    </div>
  );
}

export default AudioWaveform;