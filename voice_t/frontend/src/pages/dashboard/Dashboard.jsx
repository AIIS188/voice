import React from 'react';
import { Typography, Row, Col, Card, Button, Statistic } from 'antd';
import { Link } from 'react-router-dom';
import {
  SoundOutlined,
  AudioOutlined,
  FileTextOutlined,
  BookOutlined,
  SwapOutlined,
  UserOutlined
} from '@ant-design/icons';

const { Title, Paragraph } = Typography;

const Dashboard = () => {
  // 模拟统计数据
  const stats = {
    voices: 5,
    ttsJobs: 12,
    courseware: 3,
    replacements: 2,
  };

  // 功能卡片定义
  const features = [
    {
      title: '声音样本库',
      icon: <SoundOutlined style={{ fontSize: '32px', color: '#1890ff' }} />,
      description: '管理声音样本，上传或录制声音，提取声音特征',
      route: '/voice-library',
      color: '#e6f7ff',
    },
    {
      title: '个性化语音讲解',
      icon: <AudioOutlined style={{ fontSize: '32px', color: '#52c41a' }} />,
      description: '将文本转换为自然流畅的语音，可选择不同声音样本',
      route: '/text-to-speech',
      color: '#f6ffed',
    },
    {
      title: '标准语言输出',
      icon: <FileTextOutlined style={{ fontSize: '32px', color: '#fa8c16' }} />,
      description: '生成标准语言发音，支持语速、语调调整',
      route: '/standard-speech',
      color: '#fff7e6',
    },
    {
      title: '课件语音化',
      icon: <BookOutlined style={{ fontSize: '32px', color: '#722ed1' }} />,
      description: '上传课件文件，提取文本并生成配音，制作有声课件',
      route: '/course-voice',
      color: '#f9f0ff',
    },
    {
      title: '声音置换与字幕',
      icon: <SwapOutlined style={{ fontSize: '32px', color: '#eb2f96' }} />,
      description: '替换音视频中的声音，自动生成字幕',
      route: '/voice-replace',
      color: '#fff0f6',
    },
  ];

  return (
    <div className="dashboard">
      <div className="page-header">
        <Title level={2}>欢迎使用声教助手</Title>
        <Paragraph>
          声教助手是一款基于AI语音合成的教学声音处理软件，帮助教师和学生创建高质量的教学语音内容。
          通过简单的操作，即可实现声音克隆、语音合成、课件语音化和声音置换等功能。
        </Paragraph>
      </div>

      {/* 统计信息 */}
      <Row gutter={16} className="section">
        <Col span={6}>
          <Card>
            <Statistic
              title="声音样本"
              value={stats.voices}
              prefix={<SoundOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="语音合成任务"
              value={stats.ttsJobs}
              prefix={<AudioOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="处理课件"
              value={stats.courseware}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="声音置换"
              value={stats.replacements}
              prefix={<SwapOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 功能卡片 */}
      <Title level={3} className="section">功能导航</Title>
      <Row gutter={[16, 16]}>
        {features.map((feature, index) => (
          <Col xs={24} sm={12} md={8} key={index}>
            <Card
              hoverable
              style={{ backgroundColor: feature.color }}
              bodyStyle={{ padding: '24px' }}
            >
              <div style={{ textAlign: 'center', marginBottom: '16px' }}>
                {feature.icon}
              </div>
              <Title level={4} style={{ textAlign: 'center' }}>
                {feature.title}
              </Title>
              <Paragraph style={{ height: '60px' }}>
                {feature.description}
              </Paragraph>
              <Button type="primary" block>
                <Link to={feature.route}>立即使用</Link>
              </Button>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 快速入门 */}
      <Title level={3} className="section">快速入门</Title>
      <Row gutter={16}>
        <Col span={24}>
          <Card title="使用流程">
            <ol style={{ paddingLeft: '20px' }}>
              <li>在<strong>声音样本库</strong>中上传或录制声音样本</li>
              <li>使用<strong>个性化语音讲解</strong>将文本转换为语音</li>
              <li>或者上传课件到<strong>课件语音化</strong>生成有声课件</li>
              <li>也可以通过<strong>声音置换与字幕</strong>替换已有音视频中的声音</li>
            </ol>
            <div style={{ marginTop: '16px', textAlign: 'center' }}>
              <Button type="primary" size="large">
                <Link to="/voice-library">开始使用</Link>
              </Button>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;