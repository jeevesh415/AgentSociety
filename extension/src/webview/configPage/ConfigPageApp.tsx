import * as React from 'react';
import {
  Layout,
  Form,
  Input,
  InputNumber,
  Button,
  Card,
  Typography,
  Alert,
  Collapse,
  Select,
  Space,
} from 'antd';
import { SaveOutlined, KeyOutlined, ApiOutlined, DatabaseOutlined, ThunderboltOutlined, SettingOutlined, FolderOpenOutlined, FilePdfOutlined } from '@ant-design/icons';
import type { VSCodeAPI, ConfigValues, WorkspaceInfo } from './types';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const DEFAULT_VALUES: ConfigValues = {
  llmApiKey: '',
  backendHost: '127.0.0.1',
  backendPort: 8001,
  pythonPath: '',
  llmApiBase: 'https://cloud.infini-ai.com/maas/v1',
  llmModel: 'qwen3-next-80b-a3b-instruct',
  backendLogLevel: 'info',
  coderLlmApiKey: '',
  coderLlmApiBase: '',
  coderLlmModel: 'glm-4.7',
  nanoLlmApiKey: '',
  nanoLlmApiBase: '',
  nanoLlmModel: 'qwen3-next-80b-a3b-instruct',
  embeddingApiKey: '',
  embeddingApiBase: '',
  embeddingModel: 'bge-m3',
  embeddingDims: 1024,
  webSearchApiUrl: '',
  webSearchApiToken: '',
  miroflowDefaultLlm: 'qwen-3',
  miroflowDefaultAgent: 'mirothinker_v1.5_keep5_max200',
  easypaperApiUrl: '',
  easypaperLlmApiKey: '',
  easypaperLlmModel: 'qwen3-next-80b-a3b-instruct',
  easypaperVlmModel: 'qwen3-vl-235b-a22b-thinking',
  easypaperVlmApiKey: '',
};

interface ConfigPageAppProps {
  vscode: VSCodeAPI;
}

export const ConfigPageApp: React.FC<ConfigPageAppProps> = ({ vscode }) => {
  const [form] = Form.useForm<ConfigValues>();
  const [loading, setLoading] = React.useState(false);
  const [saveSuccess, setSaveSuccess] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [workspaceInfo, setWorkspaceInfo] = React.useState<WorkspaceInfo>({ hasWorkspace: false });

  React.useEffect(() => {
    vscode.postMessage({ command: 'requestConfig' });
  }, [vscode]);

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent<{ command: string; config?: Partial<ConfigValues>; workspaceInfo?: WorkspaceInfo }>) => {
      const message = event.data;

      if (message.command === 'initialConfig') {
        const config = message.config || {};
        form.setFieldsValue({
          ...DEFAULT_VALUES,
          ...config,
        });
      } else if (message.command === 'workspaceInfo') {
        setWorkspaceInfo(message.workspaceInfo || { hasWorkspace: false });
      } else if (message.command === 'saveResult') {
        setLoading(false);
        const msg = message as { success?: boolean; error?: string };
        if (msg.success) {
          setSaveSuccess(true);
          setError(null);
          setTimeout(() => setSaveSuccess(false), 3000);
        } else if (msg.error) {
          setError(msg.error);
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [form, vscode]);

  const handleSave = () => {
    if (!workspaceInfo.hasWorkspace) {
      setError('请先打开一个工作区文件夹（文件夹），配置将保存在当前工作区中。');
      return;
    }
    form.validateFields().then((values) => {
      setLoading(true);
      setError(null);
      vscode.postMessage({
        command: 'saveConfig',
        config: values,
      });
    });
  };

  return (
    <Layout style={{ minHeight: '100vh', background: 'var(--vscode-editor-background)' }}>
      <Content style={{ padding: '24px', maxWidth: 720, margin: '0 auto' }}>
        <div style={{ marginBottom: 24 }}>
          <Space style={{ width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div>
              <Title level={3} style={{ color: 'var(--vscode-editor-foreground)', margin: 0 }}>
                欢迎使用 AI Social Scientist
              </Title>
              <Paragraph style={{ color: 'var(--vscode-descriptionForeground)', marginBottom: 0 }}>
                请填写以下配置项以启动后端服务。所有带星号（*）的项为必填。
              </Paragraph>
            </div>
            <Button
              icon={<SettingOutlined />}
              onClick={() => vscode.postMessage({ command: 'openVscodeSettings' })}
            >
              在 VS Code 设置中编辑
            </Button>
          </Space>
        </div>

        {!workspaceInfo.hasWorkspace && (
          <Alert
            message="未检测到工作区"
            description="配置将保存在当前工作区的 .vscode/settings.json 文件中。请先打开一个工作区文件夹（File > Open Folder）。"
            type="warning"
            showIcon
            action={
              <Button
                type="primary"
                size="small"
                icon={<FolderOpenOutlined />}
                onClick={() => vscode.postMessage({ command: 'openFolder' })}
              >
                打开文件夹
              </Button>
            }
            style={{ marginBottom: 16 }}
          />
        )}

        {saveSuccess && (
          <Alert
            message="配置已保存"
            description="配置已写入 VSCode 设置。您可以在侧边栏点击「启动后端服务」来启动服务。"
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        {error && (
          <Alert
            message="保存失败"
            description={error}
            type="error"
            showIcon
            closable
            style={{ marginBottom: 16 }}
            onClose={() => setError(null)}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          initialValues={DEFAULT_VALUES}
          onFinish={handleSave}
        >
          <Card
            title={
              <Space>
                <KeyOutlined />
                <span>LLM 配置（必填）</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Form.Item
              name="llmApiKey"
              label="LLM API 密钥"
              rules={[{ required: true, message: '请输入 LLM API 密钥' }]}
            >
              <Input.Password
                placeholder="sk-xxx 或您的 API 密钥"
                size="large"
                autoComplete="off"
              />
            </Form.Item>
            <Form.Item name="llmApiBase" label="LLM API 基础 URL">
              <Input placeholder="https://cloud.infini-ai.com/maas/v1" />
            </Form.Item>
            <Form.Item name="llmModel" label="LLM 模型名称">
              <Input placeholder="qwen3-next-80b-a3b-instruct" />
            </Form.Item>
          </Card>

          <Card
            title={
              <Space>
                <ApiOutlined />
                <span>后端服务</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Form.Item name="backendHost" label="监听主机">
              <Input placeholder="127.0.0.1" />
            </Form.Item>
            <Form.Item name="backendPort" label="监听端口">
              <InputNumber min={1} max={65535} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="pythonPath" label="Python 路径（可选，留空自动检测）">
              <Input placeholder="python3 或 /usr/bin/python3" />
            </Form.Item>
          </Card>

          <Collapse ghost>
            <Panel header="高级配置（可选）" key="advanced">
              <Form.Item name="backendLogLevel" label="日志级别">
                <Select
                  options={[
                    { value: 'critical', label: 'critical' },
                    { value: 'error', label: 'error' },
                    { value: 'warning', label: 'warning' },
                    { value: 'info', label: 'info' },
                    { value: 'debug', label: 'debug' },
                    { value: 'trace', label: 'trace' },
                  ]}
                />
              </Form.Item>
              <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
                以下为代码生成、高频操作等专用 LLM 配置，留空时将使用默认 LLM 配置。
              </Text>
              <Form.Item name="coderLlmApiKey" label="代码生成 LLM API 密钥">
                <Input.Password placeholder="留空则使用默认" autoComplete="off" />
              </Form.Item>
              <Form.Item name="coderLlmApiBase" label="代码生成 LLM API 基础 URL">
                <Input placeholder="留空则使用默认" />
              </Form.Item>
              <Form.Item name="coderLlmModel" label="代码生成 LLM 模型">
                <Input placeholder="glm-4.7" />
              </Form.Item>
              <Form.Item name="nanoLlmApiKey" label="高频操作 LLM API 密钥">
                <Input.Password placeholder="留空则使用默认" autoComplete="off" />
              </Form.Item>
              <Form.Item name="nanoLlmApiBase" label="高频操作 LLM API 基础 URL">
                <Input placeholder="留空则使用默认" />
              </Form.Item>
              <Form.Item name="nanoLlmModel" label="高频操作 LLM 模型">
                <Input placeholder="qwen3-next-80b-a3b-instruct" />
              </Form.Item>
            </Panel>
            <Panel
              header={
                <Space>
                  <DatabaseOutlined />
                  <span>Embedding 模型</span>
                </Space>
              }
              key="embedding"
            >
              <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                用于文本嵌入的模型配置，留空时将使用默认 LLM 配置。
              </Text>
              <Form.Item name="embeddingApiKey" label="Embedding API 密钥">
                <Input.Password placeholder="留空则使用默认 LLM 密钥" autoComplete="off" />
              </Form.Item>
              <Form.Item name="embeddingApiBase" label="Embedding API 基础 URL">
                <Input placeholder="留空则使用默认 LLM URL" />
              </Form.Item>
              <Form.Item name="embeddingModel" label="Embedding 模型名称">
                <Input placeholder="bge-m3" />
              </Form.Item>
              <Form.Item name="embeddingDims" label="向量维度">
                <InputNumber min={64} max={4096} style={{ width: '100%' }} placeholder="1024" />
              </Form.Item>
            </Panel>
            <Panel
              header={
                <Space>
                  <ThunderboltOutlined />
                  <span>MiroFlow / MiroThinker</span>
                </Space>
              }
              key="miroflow"
            >
              <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                MiroFlow MCP 服务配置，用于高级推理任务。不使用 MiroFlow 可留空。
              </Text>
              <Form.Item name="webSearchApiUrl" label="Web 搜索 API URL">
                <Input placeholder="http://localhost:8003/mcp 或 http://localhost:8003/api/v1/search" />
              </Form.Item>
              <Form.Item name="webSearchApiToken" label="Web 搜索 API 认证令牌">
                <Input.Password placeholder="Bearer token" autoComplete="off" />
              </Form.Item>
              <Form.Item name="miroflowDefaultLlm" label="默认 LLM 模型">
                <Input placeholder="qwen-3" />
              </Form.Item>
              <Form.Item name="miroflowDefaultAgent" label="默认 Agent 配置">
                <Input placeholder="mirothinker_v1.5_keep5_max200" />
              </Form.Item>
            </Panel>
            <Panel
              header={
                <Space>
                  <FilePdfOutlined />
                  <span>EasyPaper（论文 PDF 排版）</span>
                </Space>
              }
              key="easypaper"
            >
              <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                用于 generate_paper 工具将分析报告排版成论文 PDF。需单独部署 EasyPaper 服务。填写下方模型后保存，会在工作区根目录生成 easypaper_agentsociety.yaml，启动 EasyPaper 时设置 AGENT_CONFIG_PATH 指向该文件即可统一使用此处配置。
              </Text>
              <Form.Item name="easypaperApiUrl" label="EasyPaper API URL">
                <Input placeholder="http://localhost:8004" />
              </Form.Item>
              <Form.Item name="easypaperLlmApiKey" label="EasyPaper 通用 LLM API Key">
                <Input.Password placeholder="与默认 LLM 一致可留空" autoComplete="off" />
              </Form.Item>
              <Form.Item name="easypaperLlmModel" label="EasyPaper 通用 LLM 模型（API Base 使用上方默认 LLM）">
                <Input placeholder="qwen3-next-80b-a3b-instruct" />
              </Form.Item>
              <Form.Item name="easypaperVlmModel" label="EasyPaper VLM 模型（版面检查）">
                <Input placeholder="qwen3-vl-235b-a22b-thinking" />
              </Form.Item>
              <Form.Item name="easypaperVlmApiKey" label="EasyPaper VLM API Key">
                <Input.Password placeholder="与 LLM 一致可留空" autoComplete="off" />
              </Form.Item>
            </Panel>
          </Collapse>

          <Form.Item style={{ marginTop: 24 }}>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={loading}
              size="large"
            >
              保存配置并启动后端
            </Button>
          </Form.Item>
        </Form>
      </Content>
    </Layout>
  );
};
