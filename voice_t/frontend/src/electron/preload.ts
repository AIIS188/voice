import { contextBridge, ipcRenderer } from 'electron';

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electron', {
  // 文件系统操作
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  saveFile: (data: any) => ipcRenderer.invoke('dialog:saveFile', data),
  
  // 音频处理
  playAudio: (filePath: string) => ipcRenderer.invoke('audio:play', filePath),
  stopAudio: () => ipcRenderer.invoke('audio:stop'),
  
  // 系统信息
  getSystemInfo: () => ipcRenderer.invoke('system:info'),
  
  // 窗口控制
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
}); 