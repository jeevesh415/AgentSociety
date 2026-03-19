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
  Space,
  notification,
} from 'antd';
import { SaveOutlined, KeyOutlined, ApiOutlined, CheckCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ConfigValues, WorkspaceInfo } from './types';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text } = Typography;

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
  literatureSearchApiUrl: 'http://localhost:8002/api/v1/search',
};

interface ConfigPageAppProps {
  vscode: VSCodeAPI;
}

interface ValidationState {
  validating: boolean;
  valid: boolean | null;
  error: string | null;
}

export const ConfigPageApp: React.FC<ConfigPageAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm<ConfigValues>();
  const [loading, setLoading] = React.useState(false);
  const [startingBackend, setStartingBackend] = React.useState(false);
  const [workspaceInfo, setWorkspaceInfo] = React.useState<WorkspaceInfo>({ hasWorkspace: false });

  // Validation status for each LLM type
  const [validationState, setValidationState] = React.useState<Record<string, ValidationState>>({
    default: { validating: false, valid: null, error: null },
    coder: { validating: false, valid: null, error: null },
    nano: { validating: false, valid: null, error: null },
    embedding: { validating: false, valid: null, error: null },
    easypaperVlm: { validating: false, valid: null, error: null },
    python: { validating: false, valid: null, error: null },
  });

  // Validation handler - reads current form values
  const handleValidate = async (llmType: string) => {
    const values = form.getFieldsValue();

    // Special handling for Python validation
    if (llmType === 'python') {
      setValidationState(prev => ({ ...prev, python: { validating: true, valid: null, error: null } }));
      vscode.postMessage({
        command: 'validatePython',
        config: values,
      });
      return;
    }

    // For coder/nano/embedding, check if default LLM config is filled in the form
    if (['coder', 'nano', 'embedding'].includes(llmType)) {
      if (!values.llmApiKey) {
        notification.warning({
          message: t('configPage.validationFailed'),
          description: '请先在上方配置默认 LLM API Key（留空的配置项将使用默认 LLM）',
          placement: 'top',
        });
        return;
      }
      if (!values.llmApiBase) {
        notification.warning({
          message: t('configPage.validationFailed'),
          description: '请先在上方配置默认 LLM API Base URL（留空的配置项将使用默认 LLM）',
          placement: 'top',
        });
        return;
      }
      // Don't check for missing fields - they can fall back to defaults
      setValidationState(prev => ({ ...prev, [llmType]: { validating: true, valid: null, error: null } }));
      vscode.postMessage({
        command: 'validateConfig',
        config: values,
        llmType,
      });
      return;
    }

    // For easypaperVlm, check if default LLM config is filled
    if (llmType === 'easypaperVlm') {
      if (!values.llmApiBase) {
        notification.warning({
          message: t('configPage.validationFailed'),
          description: '请先在上方配置默认 LLM API Base URL',
          placement: 'top',
        });
        return;
      }
      setValidationState(prev => ({ ...prev, [llmType]: { validating: true, valid: null, error: null } }));
      vscode.postMessage({
        command: 'validateConfig',
        config: values,
        llmType,
      });
      return;
    }

    // For default LLM, check required fields
    if (llmType === 'default') {
      const missingField = !values.llmApiKey ? 'API Key' : !values.llmApiBase ? 'API Base URL' : !values.llmModel ? '模型名称' : '';
      if (missingField) {
        notification.warning({
          message: t('configPage.validationFailed'),
          description: `请输入 ${missingField}`,
          placement: 'top',
        });
        return;
      }
      setValidationState(prev => ({ ...prev, [llmType]: { validating: true, valid: null, error: null } }));
      vscode.postMessage({
        command: 'validateConfig',
        config: values,
        llmType,
      });
      return;
    }
  };

  React.useEffect(() => {
    vscode.postMessage({ command: 'requestConfig' });
  }, [vscode]);

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data as { command: string; [key: string]: any };

      if (message.command === 'initialConfig') {
        const config = message.config || {};
        form.setFieldsValue({
          ...DEFAULT_VALUES,
          ...config,
        });
      } else if (message.command === 'workspaceInfo') {
        setWorkspaceInfo(message.workspaceInfo || { hasWorkspace: false });
      } else if (message.command === 'saveResult') {
        const msg = message as { success?: boolean; error?: string };
        setLoading(false);
        if (msg.success) {
          notification.success({
            message: t('configPage.notifications.saveSuccess'),
            description: t('configPage.notifications.saveSuccessDesc'),
            placement: 'top',
          });
        } else if (msg.error) {
          notification.error({
            message: t('configPage.notifications.saveFailed'),
            description: msg.error,
            placement: 'top',
          });
        }
      } else if (message.command === 'startBackendResult') {
        const msg = message as { success?: boolean; error?: string };
        setStartingBackend(false);
        if (msg.success) {
          notification.success({
            message: t('configPage.notifications.backendStarted', { defaultValue: 'Backend started successfully' }),
            placement: 'top',
          });
          setTimeout(() => {
            vscode.postMessage({ command: 'closeConfigPage' });
          }, 1500);
        } else if (msg.error) {
          notification.error({
            message: t('configPage.notifications.backendStartFailed', { defaultValue: 'Failed to start backend' }),
            description: msg.error,
            placement: 'top',
            duration: 6,
          });
        }
      } else if (message.command === 'validationResult') {
        const msg = message as unknown as { llmType: string; success?: boolean; error?: string };
        setValidationState(prev => ({
          ...prev,
          [msg.llmType]: { validating: false, valid: msg.success ?? false, error: msg.error || null },
        }));
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [form, vscode]);

  const handleSave = async () => {
    if (!workspaceInfo.hasWorkspace) {
      notification.warning({
        message: t('configPage.noWorkspace'),
        description: t('configPage.noWorkspaceHint'),
      });
      return;
    }

    const values = form.getFieldsValue();

    // Require LLM API key to save
    if (!values.llmApiKey) {
      notification.warning({
        message: t('configPage.notifications.llmKeyRequired'),
        description: t('configPage.notifications.llmKeyRequiredDesc'),
      });
      return;
    }

    setLoading(true);
    vscode.postMessage({
      command: 'saveConfig',
      config: values,
    });
  };

  const handleSaveAndStart = async () => {
    if (!workspaceInfo.hasWorkspace) {
      notification.warning({
        message: t('configPage.noWorkspace'),
        description: t('configPage.noWorkspaceHint'),
      });
      return;
    }

    const values = form.getFieldsValue();

    // Require LLM API key
    if (!values.llmApiKey) {
      notification.warning({
        message: t('configPage.notifications.llmKeyRequired'),
        description: t('configPage.notifications.llmKeyRequiredDesc'),
      });
      return;
    }

    setLoading(true);
    setStartingBackend(true);

    // First save, then start backend
    vscode.postMessage({
      command: 'saveConfig',
      config: values,
    });

    // Wait a bit then start backend
    setTimeout(() => {
      vscode.postMessage({
        command: 'startBackend',
        config: values,
      });
    }, 500);
  };

  return (
    <Layout style={{ minHeight: '100vh', background: 'var(--vscode-editor-background)' }}>
      <Content style={{ padding: '24px', maxWidth: 900, margin: '0 auto', width: '100%' }}>
        <div style={{ marginBottom: 24 }}>
          <Title level={2} style={{ color: 'var(--vscode-editor-foreground)' }}>
            {t('configPage.title')}
          </Title>
          <Text type="secondary" style={{ color: 'var(--vscode-descriptionForeground)' }}>
            配置您的 AgentSociety 工作区环境
          </Text>
        </div>

        {!workspaceInfo.hasWorkspace && (
          <Alert
            message={t('configPage.noWorkspace')}
            description={t('configPage.noWorkspaceHint')}
            type="warning"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}

        <Form form={form} style={{ marginBottom: 24 }}>
          {/* ========== 默认 LLM 配置 ========== */}
          <Card
            title={<><KeyOutlined /> 默认 LLM 配置</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">用于默认对话、分析等核心功能</Text>
            <Form.Item
              name="llmApiKey"
              label="LLM API 密钥 *"
              rules={[{ required: true, message: '请输入 LLM API 密钥' }]}
              style={{ marginTop: 16 }}
            >
              <Input.Password placeholder="sk-xxx 或您的 API 密钥" autoComplete="off" />
            </Form.Item>
            <Form.Item name="llmApiBase" label="LLM API 基础 URL">
              <Input placeholder="https://cloud.infini-ai.com/maas/v1" />
            </Form.Item>
            <Form.Item name="llmModel" label="LLM 模型名称">
              <Input placeholder="qwen3-next-80b-a3b-instruct" />
            </Form.Item>
            {validationState.default.error && (
              <Alert type="error" message={validationState.default.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.default.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('default')}
              loading={validationState.default?.validating}
            >
              {validationState.default?.validating ? '验证中...' : '验证'}
            </Button>
          </Card>

          {/* ========== 代码生成 LLM（可选）========== */}
          <Card
            title={<><KeyOutlined /> 代码生成 LLM（可选）</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">用于代码生成的专用模型，留空则使用默认 LLM</Text>
            <Form.Item name="coderLlmApiKey" label="代码生成 LLM API 密钥" style={{ marginTop: 16 }}>
              <Input.Password placeholder="留空则使用默认 LLM 密钥" autoComplete="off" />
            </Form.Item>
            <Form.Item name="coderLlmApiBase" label="代码生成 LLM API 基础 URL">
              <Input placeholder="留空则使用默认 LLM URL" />
            </Form.Item>
            <Form.Item name="coderLlmModel" label="代码生成 LLM 模型">
              <Input placeholder="glm-4.7" />
            </Form.Item>
            {validationState.coder.error && (
              <Alert type="error" message={validationState.coder.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.coder.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('coder')}
              loading={validationState.coder?.validating}
            >
              {validationState.coder?.validating ? '验证中...' : '验证'}
            </Button>
          </Card>

          {/* ========== 高频操作 LLM（可选）========== */}
          <Card
            title={<><KeyOutlined /> 高频操作 LLM（可选）</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">用于高频快速操作的轻量级模型</Text>
            <Form.Item name="nanoLlmApiKey" label="高频操作 LLM API 密钥" style={{ marginTop: 16 }}>
              <Input.Password placeholder="留空则使用默认" autoComplete="off" />
            </Form.Item>
            <Form.Item name="nanoLlmApiBase" label="高频操作 LLM API 基础 URL">
              <Input placeholder="留空则使用默认" />
            </Form.Item>
            <Form.Item name="nanoLlmModel" label="高频操作 LLM 模型">
              <Input placeholder="qwen3-next-80b-a3b-instruct" />
            </Form.Item>
            {validationState.nano.error && (
              <Alert type="error" message={validationState.nano.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.nano.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('nano')}
              loading={validationState.nano?.validating}
            >
              {validationState.nano?.validating ? '验证中...' : '验证'}
            </Button>
          </Card>

          {/* ========== Embedding 模型（可选）========== */}
          <Card
            title={<><ApiOutlined /> Embedding 模型（可选）</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">用于文本嵌入，留空则使用默认 LLM</Text>
            <Form.Item name="embeddingApiKey" label="Embedding API 密钥" style={{ marginTop: 16 }}>
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
            {validationState.embedding.error && (
              <Alert type="error" message={validationState.embedding.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.embedding.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('embedding')}
              loading={validationState.embedding?.validating}
            >
              {validationState.embedding?.validating ? '验证中...' : '验证'}
            </Button>
          </Card>

          {/* ========== 后端服务配置 ========== */}
          <Card
            title={<><ApiOutlined /> 后端服务配置</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">端口将自动分配，Python 路径留空则自动检测</Text>
            <Form.Item name="pythonPath" label="Python 路径（可选）" style={{ marginTop: 16 }}>
              <Input placeholder="python3 或 /usr/bin/python3" />
            </Form.Item>
            {validationState.python.error && (
              <Alert type="error" message={validationState.python.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.python.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('python')}
              loading={validationState.python?.validating}
            >
              {validationState.python?.validating ? '验证中...' : '验证 Python 环境'}
            </Button>
          </Card>

          {/* ========== EasyPaper（可选）========== */}
          <Card
            title={<><ApiOutlined /> EasyPaper（可选）</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">论文 PDF 排版服务</Text>
            <Form.Item name="easypaperApiUrl" label="EasyPaper API URL" style={{ marginTop: 16 }}>
              <Input placeholder="http://localhost:8004" />
            </Form.Item>
            <Form.Item name="easypaperLlmApiKey" label="EasyPaper 通用 LLM API Key">
              <Input.Password placeholder="与默认 LLM 一致可留空" autoComplete="off" />
            </Form.Item>
            <Form.Item name="easypaperLlmModel" label="EasyPaper LLM 模型">
              <Input placeholder="qwen3-next-80b-a3b-instruct" />
            </Form.Item>
            <Form.Item name="easypaperVlmModel" label="EasyPaper VLM 模型">
              <Input placeholder="qwen3-vl-235b-a22b-thinking" />
            </Form.Item>
            <Form.Item name="easypaperVlmApiKey" label="EasyPaper VLM API Key">
              <Input.Password placeholder="与 LLM API Key 一致可留空" autoComplete="off" />
            </Form.Item>
            {validationState.easypaperVlm.error && (
              <Alert type="error" message={validationState.easypaperVlm.error} style={{ marginBottom: 16 }} />
            )}
            {validationState.easypaperVlm.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 16 }} />
            )}
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('easypaperVlm')}
              loading={validationState.easypaperVlm?.validating}
            >
              {validationState.easypaperVlm?.validating ? '验证中...' : '验证'}
            </Button>
          </Card>

          {/* ========== 文献检索服务（可选）========== */}
          <Card
            title={<><ApiOutlined /> 文献检索服务（可选）</>}
            style={{ marginBottom: 16 }}
          >
            <Text type="secondary">学术文献检索 API</Text>
            <Form.Item name="literatureSearchApiUrl" label="文献检索 API URL" style={{ marginTop: 16 }}>
              <Input placeholder="http://localhost:8002/api/v1/search" />
            </Form.Item>
          </Card>

          {/* ========== 底部操作按钮 ========== */}
          <Card style={{ textAlign: 'center' }}>
            <Space size="large">
              <Button
                size="large"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={loading}
              >
                保存配置
              </Button>
              <Button
                type="primary"
                size="large"
                icon={<RocketOutlined />}
                onClick={handleSaveAndStart}
                loading={startingBackend}
              >
                {startingBackend ? '启动中...' : '保存并启动后端'}
              </Button>
            </Space>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">配置将保存到工作区的 .env 文件</Text>
            </div>
          </Card>
        </Form>
      </Content>
    </Layout>
  );
};
