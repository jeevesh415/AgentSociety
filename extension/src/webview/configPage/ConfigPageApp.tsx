import * as React from 'react';
import {
  ConfigProvider,
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
  Select,
  Tooltip,
  Tag,
} from 'antd';
import { SaveOutlined, KeyOutlined, CheckCircleOutlined, RocketOutlined, QuestionCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ConfigValues, WorkspaceInfo } from './types';
import { useVscodeTheme } from '../theme';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text } = Typography;
const { Panel } = Collapse;

// OpenAI 预设模板
const OPENAI_PRESET: Partial<ConfigValues> = {
  llmApiBase: 'https://api.openai.com/v1',
  llmModel: 'gpt-4o',
  coderLlmModel: 'gpt-4o',
  analysisLlmModel: 'gpt-4o',
  embeddingModel: 'text-embedding-3-large',
};

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
  analysisLlmApiKey: '',
  analysisLlmApiBase: '',
  analysisLlmModel: 'glm-5',
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
  literatureSearchApiUrl: 'http://localhost:8008/api/search',
  literatureSearchApiKey: '',
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
  const { palette, themeConfig } = useVscodeTheme();
  const [form] = Form.useForm<ConfigValues>();
  const [loading, setLoading] = React.useState(false);
  const [startingBackend, setStartingBackend] = React.useState(false);
  const [workspaceInfo, setWorkspaceInfo] = React.useState<WorkspaceInfo>({ hasWorkspace: false });

  // Validation status for each LLM type
  const [validationState, setValidationState] = React.useState<Record<string, ValidationState>>({
    default: { validating: false, valid: null, error: null },
    coder: { validating: false, valid: null, error: null },
    nano: { validating: false, valid: null, error: null },
    analysis: { validating: false, valid: null, error: null },
    embedding: { validating: false, valid: null, error: null },
    easypaperVlm: { validating: false, valid: null, error: null },
    python: { validating: false, valid: null, error: null },
    literature: { validating: false, valid: null, error: null },
  });

  // Reset to default values
  const handleResetDefaults = () => {
    form.setFieldsValue(DEFAULT_VALUES);
    notification.info({
      message: t('configPage.resetDefaults'),
      placement: 'top',
    });
  };

  // Apply OpenAI preset
  const handleApplyOpenAIPreset = () => {
    const currentValues = form.getFieldsValue();
    form.setFieldsValue({
      ...currentValues,
      ...OPENAI_PRESET,
    });
    notification.info({
      message: 'OpenAI 预设已应用',
      placement: 'top',
    });
  };

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

    // For coder/nano/analysis/embedding, check if default LLM config is filled in the form
    if (['coder', 'nano', 'analysis', 'embedding'].includes(llmType)) {
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

    // For literature search, validate API URL and Key
    if (llmType === 'literature') {
      if (!values.literatureSearchApiUrl) {
        notification.warning({
          message: t('configPage.validationFailed'),
          description: '请输入文献检索 API URL',
          placement: 'top',
        });
        return;
      }
      setValidationState(prev => ({ ...prev, [llmType]: { validating: true, valid: null, error: null } }));
      vscode.postMessage({
        command: 'validateLiteratureSearch',
        config: values,
      });
      return;
    }
  };

  React.useEffect(() => {
    vscode.postMessage({ command: 'requestConfig' });
  }, [vscode]);

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data as { command: string;[key: string]: any };

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
      } else if (message.command === 'literatureValidationResult') {
        const msg = message as { success?: boolean; error?: string; sources?: Record<string, unknown> };
        setValidationState(prev => ({
          ...prev,
          literature: { validating: false, valid: msg.success ?? false, error: msg.error || null },
        }));
        if (msg.success && msg.sources) {
          notification.success({
            message: '文献检索配置验证成功',
            description: `服务已连接，数据源: ${Object.keys(msg.sources).join(', ')}`,
            placement: 'top',
          });
        }
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
    <ConfigProvider theme={themeConfig}>
      <Layout style={{ minHeight: '100vh', background: palette.editorBackground }}>
        <Content
          style={{
            padding: '24px',
            maxWidth: 900,
            margin: '0 auto',
            width: '100%',
            color: palette.editorForeground,
          }}
        >
        <div style={{ marginBottom: 24 }}>
          <Title level={2} style={{ color: palette.editorForeground }}>
            {t('configPage.title')}
          </Title>
          <Text type="secondary" style={{ color: palette.descriptionForeground }}>
            {t('configPage.subtitle')}
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
          <Card 
            title={
              <Space>
                <KeyOutlined />
                <span>LLM 配置</span>
                <Tag color="red">必填</Tag>
              </Space>
            }
            extra={
              <Button size="small" onClick={handleApplyOpenAIPreset}>
                OpenAI 预设
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Form.Item
              name="llmApiKey"
              label={t('configPage.llm.apiKeyRequired')}
              rules={[{ required: true, message: t('configPage.notifications.apiKeyMissing') }]}
              tooltip={t('configPage.llm.apiKeyRequiredHint')}
            >
              <Input.Password placeholder={t('configPage.llm.apiKeyPlaceholder')} autoComplete="off" />
            </Form.Item>
            <Form.Item name="llmApiBase" label={t('configPage.llm.apiBase')}>
              <Input placeholder={t('configPage.llm.apiBasePlaceholder')} />
            </Form.Item>
            <Form.Item name="llmModel" label={t('configPage.llm.modelName')}>
              <Input placeholder={t('configPage.llm.modelPlaceholder')} />
            </Form.Item>
            {validationState.default.error && (
              <Alert type="error" message={t('configPage.validationFailed')} description={validationState.default.error} style={{ marginBottom: 12 }} />
            )}
            {validationState.default.valid && (
              <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 12 }} />
            )}
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => handleValidate('default')}
              loading={validationState.default?.validating}
            >
              {t('configPage.validate')}
            </Button>
          </Card>

          {/* ========== 可选配置（折叠）========== */}
          <Collapse bordered={false} style={{ marginBottom: 16 }}>
            <Panel header={t('configPage.advancedConfig')} key="advanced">
              {/* 代码生成 LLM */}
              <Card size="small" title={t('configPage.coder.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.coder.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="coderLlmApiKey" label={t('configPage.coder.apiKey')}>
                  <Input.Password placeholder={t('configPage.coder.apiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item name="coderLlmApiBase" label={t('configPage.coder.apiBase')}>
                  <Input placeholder={t('configPage.coder.apiBasePlaceholder')} />
                </Form.Item>
                <Form.Item name="coderLlmModel" label={t('configPage.coder.model')}>
                  <Input placeholder={t('configPage.coder.modelPlaceholder')} />
                </Form.Item>
                {validationState.coder.error && <Alert type="error" message={t('configPage.validationFailed')} description={validationState.coder.error} style={{ marginBottom: 8 }} />}
                {validationState.coder.valid && <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('coder')} loading={validationState.coder?.validating}>{t('configPage.validate')}</Button>
              </Card>

              {/* 高频操作 LLM */}
              <Card size="small" title={t('configPage.advanced.nano.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.advanced.nano.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="nanoLlmApiKey" label={t('configPage.advanced.nano.apiKey')}>
                  <Input.Password placeholder={t('configPage.advanced.nano.apiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item name="nanoLlmApiBase" label={t('configPage.advanced.nano.apiBase')}>
                  <Input placeholder={t('configPage.advanced.nano.apiBasePlaceholder')} />
                </Form.Item>
                <Form.Item name="nanoLlmModel" label={t('configPage.advanced.nano.model')}>
                  <Input placeholder={t('configPage.advanced.nano.modelPlaceholder')} />
                </Form.Item>
                {validationState.nano.error && <Alert type="error" message={t('configPage.validationFailed')} description={validationState.nano.error} style={{ marginBottom: 8 }} />}
                {validationState.nano.valid && <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('nano')} loading={validationState.nano?.validating}>{t('configPage.validate')}</Button>
              </Card>

              {/* 分析 LLM */}
              <Card size="small" title={t('configPage.analysis.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.analysis.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="analysisLlmApiKey" label={t('configPage.analysis.apiKey')}>
                  <Input.Password placeholder={t('configPage.analysis.apiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item name="analysisLlmApiBase" label={t('configPage.analysis.apiBase')}>
                  <Input placeholder={t('configPage.analysis.apiBasePlaceholder')} />
                </Form.Item>
                <Form.Item name="analysisLlmModel" label={t('configPage.analysis.model')}>
                  <Input placeholder={t('configPage.analysis.modelPlaceholder')} />
                </Form.Item>
                {validationState.analysis?.error && <Alert type="error" message={t('configPage.validationFailed')} description={validationState.analysis.error} style={{ marginBottom: 8 }} />}
                {validationState.analysis?.valid && <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('analysis')} loading={validationState.analysis?.validating}>{t('configPage.validate')}</Button>
              </Card>

              {/* Embedding */}
              <Card size="small" title={t('configPage.advanced.embedding.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.advanced.embedding.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="embeddingApiKey" label={t('configPage.advanced.embedding.apiKey')}>
                  <Input.Password placeholder={t('configPage.advanced.embedding.apiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item name="embeddingApiBase" label={t('configPage.advanced.embedding.apiBase')}>
                  <Input placeholder={t('configPage.advanced.embedding.apiBasePlaceholder')} />
                </Form.Item>
                <Form.Item name="embeddingModel" label={t('configPage.advanced.embedding.model')}>
                  <Input placeholder={t('configPage.advanced.embedding.modelPlaceholder')} />
                </Form.Item>
                <Form.Item name="embeddingDims" label={t('configPage.advanced.embedding.dims')}>
                  <InputNumber min={64} max={4096} style={{ width: '100%' }} placeholder={t('configPage.advanced.embedding.dimsPlaceholder')} />
                </Form.Item>
                {validationState.embedding.error && <Alert type="error" message={t('configPage.validationFailed')} description={validationState.embedding.error} style={{ marginBottom: 8 }} />}
                {validationState.embedding.valid && <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('embedding')} loading={validationState.embedding?.validating}>{t('configPage.validate')}</Button>
              </Card>

              {/* Python 环境 */}
              <Card size="small" title={t('configPage.python.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.python.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="pythonPath" label={t('configPage.python.path')}>
                  <Input placeholder={t('configPage.python.pathPlaceholder')} />
                </Form.Item>
                {validationState.python.error && <Alert type="error" message={t('configPage.validationFailed')} description={validationState.python.error} style={{ marginBottom: 8 }} />}
                {validationState.python.valid && <Alert type="success" message={t('configPage.validationSuccess')} style={{ marginBottom: 8 }} />}
                <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleValidate('python')} loading={validationState.python?.validating}>{t('configPage.validate')}</Button>
              </Card>

              {/* EasyPaper */}
              <Card size="small" title={t('configPage.advanced.easypaper.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.advanced.easypaper.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="easypaperApiUrl" label={t('configPage.advanced.easypaper.apiUrl')}>
                  <Input placeholder={t('configPage.advanced.easypaper.apiUrlPlaceholder')} />
                </Form.Item>
                <Form.Item name="easypaperLlmApiKey" label={t('configPage.advanced.easypaper.llmApiKey')}>
                  <Input.Password placeholder={t('configPage.advanced.easypaper.llmApiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item name="easypaperLlmModel" label={t('configPage.advanced.easypaper.llmModel')}>
                  <Input placeholder={t('configPage.advanced.easypaper.llmModelPlaceholder')} />
                </Form.Item>
                <Form.Item name="easypaperVlmModel" label={t('configPage.advanced.easypaper.vlmModel')}>
                  <Input placeholder={t('configPage.advanced.easypaper.vlmModelPlaceholder')} />
                </Form.Item>
                <Form.Item name="easypaperVlmApiKey" label={t('configPage.advanced.easypaper.vlmApiKey')}>
                  <Input.Password placeholder={t('configPage.advanced.easypaper.vlmApiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
              </Card>

              {/* 文献检索 */}
              <Card size="small" title={t('configPage.literature.title')} style={{ marginBottom: 12 }} extra={<Tooltip title={t('configPage.literature.hint')}><QuestionCircleOutlined /></Tooltip>}>
                <Form.Item name="literatureSearchApiUrl" label={t('configPage.advanced.literature.apiUrl')}>
                  <Input placeholder={t('configPage.advanced.literature.apiUrlPlaceholder')} />
                </Form.Item>
                <Form.Item name="literatureSearchApiKey" label="API Key">
                  <Input.Password placeholder="lit-xxx" autoComplete="off" />
                </Form.Item>
                <Form.Item>
                  <Space>
                    <Button
                      size="small"
                      icon={<CheckCircleOutlined />}
                      loading={validationState.literature?.validating}
                      onClick={() => handleValidate('literature')}
                    >
                      {t('configPage.literature.validateConfig')}
                    </Button>
                    {validationState.literature?.valid === true && (
                      <Text type="success">✓ {t('configPage.literature.validateSuccess')}</Text>
                    )}
                    {validationState.literature?.valid === false && (
                      <Text type="danger">✗ {validationState.literature.error}</Text>
                    )}
                  </Space>
                </Form.Item>
              </Card>
            </Panel>
          </Collapse>

          {/* ========== 操作按钮 ========== */}
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <Space size="large">
              <Button
                size="large"
                icon={<ReloadOutlined />}
                onClick={handleResetDefaults}
              >
                {t('configPage.resetDefaults')}
              </Button>
              <Button
                size="large"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={loading}
              >
                {t('configPage.save')}
              </Button>
              <Button
                type="primary"
                size="large"
                icon={<RocketOutlined />}
                onClick={handleSaveAndStart}
                loading={startingBackend}
              >
                {startingBackend ? t('configPage.starting') : t('configPage.saveAndStart')}
              </Button>
            </Space>
          </div>
        </Form>
        </Content>
      </Layout>
    </ConfigProvider>
  );
};
