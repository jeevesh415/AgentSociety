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
  Collapse,
} from 'antd';
import { SaveOutlined, KeyOutlined, CheckCircleOutlined, RocketOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ConfigValues, WorkspaceInfo } from './types';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text } = Typography;
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
          {/* ========== 必填配置 ========== */}
          <Card title={<><KeyOutlined /> LLM 配置</>} style={{ marginBottom: 16 }}>
            <Form.Item
              name="llmApiKey"
              label="API 密钥 *"
              rules={[{ required: true, message: '请输入 API 密钥' }]}
            >
              <Input.Password placeholder="sk-xxx 或您的 API 密钥" autoComplete="off" />
            </Form.Item>
            <Form.Item name="llmApiBase" label="API 基础 URL">
              <Input placeholder="https://cloud.infini-ai.com/maas/v1" />
            </Form.Item>
            <Form.Item name="llmModel" label="模型名称">
              <Input placeholder="qwen3-next-80b-a3b-instruct" />
            </Form.Item>
            {validationState.default.error && (
              <Alert type="error" message={validationState.default.error} style={{ marginBottom: 12 }} />
            )}
            {validationState.default.valid && (
              <Alert type="success" message="验证成功" style={{ marginBottom: 12 }} />
            )}
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('default')}
              loading={validationState.default?.validating}
            >
              验证
            </Button>
          </Card>

          {/* ========== 可选配置（折叠）========== */}
          <Collapse bordered={false} style={{ marginBottom: 16 }}>
            <Panel header="高级配置（可选）" key="advanced">
              {/* 代码生成 LLM */}
              <Card size="small" title="代码生成 LLM" style={{ marginBottom: 12 }}>
                <Form.Item name="coderLlmApiKey" label="API 密钥">
                  <Input.Password placeholder="留空使用默认" autoComplete="off" />
                </Form.Item>
                <Form.Item name="coderLlmApiBase" label="API URL">
                  <Input placeholder="留空使用默认" />
                </Form.Item>
                <Form.Item name="coderLlmModel" label="模型">
                  <Input placeholder="glm-4.7" />
                </Form.Item>
                {validationState.coder.error && <Alert type="error" message={validationState.coder.error} style={{ marginBottom: 8 }} />}
                {validationState.coder.valid && <Alert type="success" message="验证成功" style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('coder')} loading={validationState.coder?.validating}>验证</Button>
              </Card>

              {/* 高频操作 LLM */}
              <Card size="small" title="高频操作 LLM" style={{ marginBottom: 12 }}>
                <Form.Item name="nanoLlmApiKey" label="API 密钥">
                  <Input.Password placeholder="留空使用默认" autoComplete="off" />
                </Form.Item>
                <Form.Item name="nanoLlmApiBase" label="API URL">
                  <Input placeholder="留空使用默认" />
                </Form.Item>
                <Form.Item name="nanoLlmModel" label="模型">
                  <Input placeholder="qwen3-next-80b-a3b-instruct" />
                </Form.Item>
                {validationState.nano.error && <Alert type="error" message={validationState.nano.error} style={{ marginBottom: 8 }} />}
                {validationState.nano.valid && <Alert type="success" message="验证成功" style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('nano')} loading={validationState.nano?.validating}>验证</Button>
              </Card>

              {/* Embedding */}
              <Card size="small" title="Embedding 模型" style={{ marginBottom: 12 }}>
                <Form.Item name="embeddingApiKey" label="API 密钥">
                  <Input.Password placeholder="留空使用默认" autoComplete="off" />
                </Form.Item>
                <Form.Item name="embeddingApiBase" label="API URL">
                  <Input placeholder="留空使用默认" />
                </Form.Item>
                <Form.Item name="embeddingModel" label="模型">
                  <Input placeholder="bge-m3" />
                </Form.Item>
                <Form.Item name="embeddingDims" label="向量维度">
                  <InputNumber min={64} max={4096} style={{ width: '100%' }} placeholder="1024" />
                </Form.Item>
                {validationState.embedding.error && <Alert type="error" message={validationState.embedding.error} style={{ marginBottom: 8 }} />}
                {validationState.embedding.valid && <Alert type="success" message="验证成功" style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('embedding')} loading={validationState.embedding?.validating}>验证</Button>
              </Card>

              {/* Python 环境 */}
              <Card size="small" title="Python 环境" style={{ marginBottom: 12 }}>
                <Form.Item name="pythonPath" label="Python 路径">
                  <Input placeholder="python3 或留空自动检测" />
                </Form.Item>
                {validationState.python.error && <Alert type="error" message={validationState.python.error} style={{ marginBottom: 8 }} />}
                {validationState.python.valid && <Alert type="success" message="验证成功" style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('python')} loading={validationState.python?.validating}>验证</Button>
              </Card>

              {/* EasyPaper */}
              <Card size="small" title="EasyPaper（论文排版）" style={{ marginBottom: 12 }}>
                <Form.Item name="easypaperApiUrl" label="API URL">
                  <Input placeholder="http://localhost:8004" />
                </Form.Item>
                <Form.Item name="easypaperLlmApiKey" label="LLM API Key">
                  <Input.Password placeholder="与默认一致可留空" autoComplete="off" />
                </Form.Item>
                <Form.Item name="easypaperLlmModel" label="LLM 模型">
                  <Input placeholder="qwen3-next-80b-a3b-instruct" />
                </Form.Item>
                <Form.Item name="easypaperVlmModel" label="VLM 模型">
                  <Input placeholder="qwen3-vl-235b-a22b-thinking" />
                </Form.Item>
                <Form.Item name="easypaperVlmApiKey" label="VLM API Key">
                  <Input.Password placeholder="与 LLM 一致可留空" autoComplete="off" />
                </Form.Item>
              </Card>

              {/* 文献检索 */}
              <Card size="small" title="文献检索">
                <Form.Item name="literatureSearchApiUrl" label="API URL">
                  <Input placeholder="http://localhost:8002/api/v1/search" />
                </Form.Item>
              </Card>
            </Panel>
          </Collapse>

          {/* ========== 操作按钮 ========== */}
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <Space size="large">
              <Button
                size="large"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={loading}
              >
                保存
              </Button>
              <Button
                type="primary"
                size="large"
                icon={<RocketOutlined />}
                onClick={handleSaveAndStart}
                loading={startingBackend}
              >
                {startingBackend ? '启动中...' : '保存并启动'}
              </Button>
            </Space>
          </div>
        </Form>
      </Content>
    </Layout>
  );
};
