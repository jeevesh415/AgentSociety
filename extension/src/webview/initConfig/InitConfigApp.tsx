import * as React from 'react';
import {
  ConfigProvider,
  theme,
  Card,
  Typography,
  Space,
  Button,
  Table,
  Collapse,
  Tag,
  Input,
  InputNumber,
  Select,
  Spin,
  Alert,
  Statistic,
  Row,
  Col,
  Empty,
  Popconfirm,
  message,
} from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  PlusOutlined,
  SettingOutlined,
  UserOutlined,
  EnvironmentOutlined,
  EditOutlined,
} from '@ant-design/icons';
import type { VSCodeAPI, InitConfig, EnvModuleConfig, AgentConfig } from './types';
import '../i18n';

const { Title, Text } = Typography;
const { Panel } = Collapse;

interface InitConfigAppProps {
  vscode: VSCodeAPI;
  initialConfig?: InitConfig;
}

// 判断是否为简单类型
const isSimpleType = (value: any): boolean => {
  return (
    value === null ||
    value === undefined ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  );
};

// 渲染单个参数的编辑器
const ParamEditor: React.FC<{
  value: any;
  onChange: (value: any) => void;
  depth?: number;
}> = ({ value, onChange, depth = 0 }) => {
  if (value === null || value === undefined) {
    return <Text type="secondary">null</Text>;
  }

  if (typeof value === 'boolean') {
    return (
      <Select
        value={value}
        onChange={onChange}
        size="small"
        style={{ width: 80 }}
        options={[
          { value: true, label: 'true' },
          { value: false, label: 'false' },
        ]}
      />
    );
  }

  if (typeof value === 'number') {
    return (
      <InputNumber
        value={value}
        onChange={(v) => onChange(v)}
        size="small"
        style={{ width: 120 }}
      />
    );
  }

  if (typeof value === 'string') {
    // 如果字符串较长，使用文本域
    if (value.length > 50) {
      return (
        <Input.TextArea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          size="small"
          autoSize={{ minRows: 2, maxRows: 6 }}
        />
      );
    }
    return (
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        size="small"
        style={{ width: '100%', maxWidth: 300 }}
      />
    );
  }

  if (Array.isArray(value)) {
    return (
      <div style={{ marginTop: 8 }}>
        {value.map((item, index) => (
          <div key={index} style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
            <ParamEditor
              value={item}
              onChange={(v) => {
                const newArr = [...value];
                newArr[index] = v;
                onChange(newArr);
              }}
              depth={depth + 1}
            />
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            />
          </div>
        ))}
        <Button
          size="small"
          type="dashed"
          icon={<PlusOutlined />}
          onClick={() => onChange([...value, ''])}
        >
          添加
        </Button>
      </div>
    );
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value);
    return (
      <div style={{ paddingLeft: depth > 0 ? 12 : 0, borderLeft: depth > 0 ? '2px solid #d9d9d9' : 'none' }}>
        {keys.map((key) => (
          <div key={key} style={{ marginBottom: 8 }}>
            <Text strong style={{ marginRight: 8 }}>
              {key}:
            </Text>
            <ParamEditor
              value={value[key]}
              onChange={(v) => onChange({ ...value, [key]: v })}
              depth={depth + 1}
            />
          </div>
        ))}
      </div>
    );
  }

  return <Text>{String(value)}</Text>;
};

export const InitConfigApp: React.FC<InitConfigAppProps> = ({ vscode, initialConfig }) => {
  const [config, setConfig] = React.useState<InitConfig>(initialConfig || {});
  const [loading, setLoading] = React.useState<boolean>(true);
  const [saved, setSaved] = React.useState<boolean>(false);

  // 组件挂载时请求数据
  React.useEffect(() => {
    vscode.postMessage({ command: 'requestData' });
  }, [vscode]);

  // 监听来自扩展的消息
  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      if (message.command === 'initialData' || message.command === 'update') {
        let newConfig: InitConfig = {};
        if (message.config) {
          newConfig = message.config;
        } else if (message.text) {
          try {
            newConfig = JSON.parse(message.text);
          } catch (e) {
            console.error('Error parsing config:', e);
          }
        }
        setConfig(newConfig);
        setLoading(false);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // 保存配置
  const handleSave = () => {
    vscode.postMessage({
      command: 'save',
      content: JSON.stringify(config, null, 2),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // 更新环境模块参数
  const updateEnvModule = (index: number, updates: Partial<EnvModuleConfig>) => {
    const newModules = [...(config.env_modules || [])];
    newModules[index] = { ...newModules[index], ...updates };
    setConfig({ ...config, env_modules: newModules });
  };

  // 更新 Agent 参数
  const updateAgent = (index: number, updates: Partial<AgentConfig>) => {
    const newAgents = [...(config.agents || [])];
    newAgents[index] = { ...newAgents[index], ...updates };
    setConfig({ ...config, agents: newAgents });
  };

  // 更新 Agent kwargs
  const updateAgentKwargs = (index: number, key: string, value: any) => {
    const newAgents = [...(config.agents || [])];
    newAgents[index] = {
      ...newAgents[index],
      kwargs: { ...newAgents[index].kwargs, [key]: value },
    };
    setConfig({ ...config, agents: newAgents });
  };

  // 删除环境模块
  const deleteEnvModule = (index: number) => {
    const newModules = (config.env_modules || []).filter((_, i) => i !== index);
    setConfig({ ...config, env_modules: newModules });
  };

  // 删除 Agent
  const deleteAgent = (index: number) => {
    const newAgents = (config.agents || []).filter((_, i) => i !== index);
    setConfig({ ...config, agents: newAgents });
  };

  // 适配 VSCode 主题
  const isDark: boolean =
    document.body.classList.contains('vscode-dark') ||
    document.body.classList.contains('vscode-high-contrast');

  const themeConfig = React.useMemo(
    () => ({
      algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    }),
    [isDark]
  );

  if (loading) {
    return (
      <ConfigProvider theme={themeConfig}>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            gap: 16,
          }}
        >
          <Spin size="large" />
          <Text>加载配置中...</Text>
        </div>
      </ConfigProvider>
    );
  }

  const envModules = config.env_modules || [];
  const agents = config.agents || [];

  return (
    <ConfigProvider theme={themeConfig}>
      <div style={{ padding: 24, minHeight: '100vh' }}>
        <Title level={2} style={{ marginBottom: 24 }}>
          实验初始化配置
        </Title>

        {saved && (
          <Alert
            message="配置已保存"
            type="success"
            showIcon
            closable
            style={{ marginBottom: 16 }}
            onClose={() => setSaved(false)}
          />
        )}

        {/* 统计卡片 */}
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={8}>
            <Card>
              <Statistic
                title="环境模块"
                value={envModules.length}
                prefix={<EnvironmentOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="Agent 数量"
                value={agents.length}
                prefix={<UserOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="配置状态"
                value={envModules.length > 0 && agents.length > 0 ? '完整' : '不完整'}
                valueStyle={{
                  color: envModules.length > 0 && agents.length > 0 ? '#52c41a' : '#faad14',
                }}
              />
            </Card>
          </Col>
        </Row>

        {/* 环境模块区域 */}
        <Card
          title={
            <Space>
              <EnvironmentOutlined />
              环境模块配置
              <Tag color="blue">{envModules.length}</Tag>
            </Space>
          }
          style={{ marginBottom: 24 }}
        >
          {envModules.length === 0 ? (
            <Empty description="暂无环境模块配置" />
          ) : (
            <Collapse accordion>
              {envModules.map((module, index) => (
                <Panel
                  header={
                    <Space>
                      <Tag color="green">{module.module_type}</Tag>
                      <Text type="secondary">
                        {Object.keys(module.kwargs || {}).length} 个参数
                      </Text>
                    </Space>
                  }
                  key={index}
                  extra={
                    <Popconfirm
                      title="确定删除此模块？"
                      onConfirm={() => deleteEnvModule(index)}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>
                  }
                >
                  <div style={{ padding: '12px 0' }}>
                    <Text strong style={{ display: 'block', marginBottom: 12 }}>
                      模块类型: {module.module_type}
                    </Text>
                    <Card size="small" title="参数配置" style={{ marginBottom: 12 }}>
                      <ParamEditor
                        value={module.kwargs}
                        onChange={(newKwargs) => updateEnvModule(index, { kwargs: newKwargs })}
                      />
                    </Card>
                  </div>
                </Panel>
              ))}
            </Collapse>
          )}
        </Card>

        {/* Agent 区域 */}
        <Card
          title={
            <Space>
              <UserOutlined />
              Agent 配置
              <Tag color="blue">{agents.length}</Tag>
            </Space>
          }
          style={{ marginBottom: 24 }}
        >
          {agents.length === 0 ? (
            <Empty description="暂无 Agent 配置" />
          ) : (
            <Table
              dataSource={agents.map((agent, index) => ({ ...agent, _index: index }))}
              rowKey="agent_id"
              pagination={false}
              size="small"
              expandable={{
                expandedRowRender: (record) => (
                  <div style={{ padding: 12 }}>
                    <Card size="small" title="Kwargs 参数" style={{ marginBottom: 12 }}>
                      <ParamEditor
                        value={record.kwargs}
                        onChange={(newKwargs) => updateAgent(record._index, { kwargs: newKwargs })}
                      />
                    </Card>
                    {record.kwargs?.profile && (
                      <Card size="small" title="Profile">
                        <ParamEditor
                          value={record.kwargs.profile}
                          onChange={(newProfile) =>
                            updateAgentKwargs(record._index, 'profile', newProfile)
                          }
                        />
                      </Card>
                    )}
                  </div>
                ),
              }}
              columns={[
                {
                  title: 'ID',
                  dataIndex: 'agent_id',
                  width: 60,
                },
                {
                  title: '类型',
                  dataIndex: 'agent_type',
                  width: 180,
                  render: (text) => <Tag color="blue">{text}</Tag>,
                },
                {
                  title: '名称',
                  dataIndex: ['kwargs', 'name'],
                  ellipsis: true,
                },
                {
                  title: '角色',
                  dataIndex: ['kwargs', 'role'],
                  width: 100,
                  render: (text) => text && <Tag>{text}</Tag>,
                },
                {
                  title: '操作',
                  width: 80,
                  render: (_, record) => (
                    <Popconfirm
                      title="确定删除此 Agent？"
                      onConfirm={() => deleteAgent(record._index)}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  ),
                },
              ]}
            />
          )}
        </Card>

        {/* 保存按钮 */}
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Space>
            <Button size="large" onClick={() => setConfig(initialConfig || {})}>
              重置
            </Button>
            <Button type="primary" size="large" icon={<SaveOutlined />} onClick={handleSave}>
              保存配置
            </Button>
          </Space>
        </div>
      </div>
    </ConfigProvider>
  );
};
