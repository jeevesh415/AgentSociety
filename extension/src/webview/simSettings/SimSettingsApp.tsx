import * as React from 'react';
import { ConfigProvider, theme, Transfer, Button, Space, Typography, Card, Alert, Spin, Modal } from 'antd';
import { SaveOutlined, ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, SimSettings, AgentInfo, EnvModuleInfo } from './types';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import '../i18n';

const { Title, Text } = Typography;

// 截取描述预览文本
const getDescriptionPreview = (description: string, maxLength: number = 150): string => {
  if (!description) return '';
  // 移除 markdown 格式标记
  const plainText = description.replace(/[#*`_\[\]()]/g, '').replace(/\n/g, ' ').trim();
  if (plainText.length <= maxLength) return plainText;
  return plainText.substring(0, maxLength) + '...';
};

interface SimSettingsAppProps {
  vscode: VSCodeAPI;
  initialSettings?: SimSettings;
}

export const SimSettingsApp: React.FC<SimSettingsAppProps> = ({
  vscode,
  initialSettings,
}: SimSettingsAppProps) => {
  const { t } = useTranslation();
  const [agentClasses, setAgentClasses] = React.useState<Record<string, AgentInfo>>({});
  const [envModules, setEnvModules] = React.useState<Record<string, EnvModuleInfo>>({});
  const [loading, setLoading] = React.useState<boolean>(true);
  const [agentClassesList, setAgentClassesList] = React.useState<string[]>(
    initialSettings?.agentClasses || []
  );
  const [envModulesList, setEnvModulesList] = React.useState<string[]>(
    initialSettings?.envModules || []
  );
  const [saved, setSaved] = React.useState<boolean>(false);
  const [descriptionModalVisible, setDescriptionModalVisible] = React.useState<boolean>(false);
  const [currentDescription, setCurrentDescription] = React.useState<{ title: string; content: string } | null>(null);

  // 组件挂载时请求数据
  React.useEffect(() => {
    // 请求 agent classes 和 env modules 数据
    vscode.postMessage({
      command: 'requestData',
    });
  }, [vscode]);

  // 监听来自扩展的消息
  React.useEffect(() => {
    const handleMessage = (event: MessageEvent<any>) => {
      const message = event.data;

      if (message.command === 'initialData') {
        // 接收初始数据
        if (message.agentClasses) {
          setAgentClasses(message.agentClasses);
        }
        if (message.envModules) {
          setEnvModules(message.envModules);
        }
        if (message.settings) {
          const settings: SimSettings = message.settings;
          // 更新 agent classes 列表
          if (settings.agentClasses && Array.isArray(settings.agentClasses)) {
            setAgentClassesList(settings.agentClasses);
          } else {
            setAgentClassesList([]);
          }
          // 更新 env modules 列表
          if (settings.envModules && Array.isArray(settings.envModules)) {
            setEnvModulesList(settings.envModules);
          } else {
            setEnvModulesList([]);
          }
        }
        setLoading(false);
      } else if (message.command === 'update') {
        // 更新设置
        try {
          const settings: SimSettings = JSON.parse(message.text || '{}');

          // 更新 agent classes
          if (settings.agentClasses && Array.isArray(settings.agentClasses)) {
            setAgentClassesList(settings.agentClasses);
          } else {
            setAgentClassesList([]);
          }

          // 更新 env modules
          if (settings.envModules && Array.isArray(settings.envModules)) {
            setEnvModulesList(settings.envModules);
          } else {
            setEnvModulesList([]);
          }
        } catch (e) {
          console.error('Error parsing settings:', e);
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const handleSave = () => {
    // 只保存配置相关的字段
    const settings: SimSettings = {
      agentClasses: agentClassesList,
      envModules: envModulesList,
    };

    vscode.postMessage({
      command: 'save',
      content: JSON.stringify(settings, null, 2),
    });

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleLoadDefaults = () => {
    setAgentClassesList([]);
    setEnvModulesList([]);
  };

  const handleViewDescription = (type: string, isAgent: boolean) => {
    const info = isAgent ? agentClasses[type] : envModules[type];
    if (info && info.description) {
      setCurrentDescription({
        title: `${type} (${info.class_name})`,
        content: info.description,
      });
      setDescriptionModalVisible(true);
    }
  };

  const handleCloseDescriptionModal = () => {
    setDescriptionModalVisible(false);
    setCurrentDescription(null);
  };

  // 适配 VSCode 主题
  const isDark: boolean =
    document.body.classList.contains('vscode-dark') ||
    document.body.classList.contains('vscode-high-contrast');

  // 使用 ant-design 默认主题，只设置算法（dark/light）
  const themeConfig = React.useMemo(() => ({
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
  }), [isDark]);

  // 准备 Transfer 数据源
  const agentDataSource = Object.keys(agentClasses).map(type => ({
    key: type,
    title: type,
    class_name: agentClasses[type].class_name,
    description: agentClasses[type].description || '',
  }));

  const envModuleDataSource = Object.keys(envModules).map(type => ({
    key: type,
    title: type,
    class_name: envModules[type].class_name,
    description: envModules[type].description || '',
  }));

  // 自定义渲染函数 - Agent Classes
  const renderAgentItem = (item: typeof agentDataSource[0]) => {
    const preview = getDescriptionPreview(item.description);
    return (
      <Card
        size="small"
        hoverable={!!item.description}
        style={{
          marginBottom: '8px',
          cursor: item.description ? 'pointer' : 'default',
        }}
        bodyStyle={{
          padding: '12px',
        }}
        onClick={() => {
          if (item.description) {
            handleViewDescription(item.key, true);
          }
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Text strong style={{ fontSize: '13px' }}>
              {item.title}
            </Text>
            {item.description && (
              <InfoCircleOutlined
                style={{
                  fontSize: '14px',
                  flexShrink: 0,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleViewDescription(item.key, true);
                }}
              />
            )}
          </div>
          <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>
            {item.class_name}
          </Text>
          {preview && (
            <Text
              type="secondary"
              style={{
                fontSize: '12px',
                display: 'block',
                lineHeight: '1.4',
              }}
            >
              {preview}
            </Text>
          )}
        </Space>
      </Card>
    );
  };

  // 自定义渲染函数 - Env Modules
  const renderEnvModuleItem = (item: typeof envModuleDataSource[0]) => {
    const preview = getDescriptionPreview(item.description);
    return (
      <Card
        size="small"
        hoverable={!!item.description}
        style={{
          marginBottom: '8px',
          cursor: item.description ? 'pointer' : 'default',
        }}
        bodyStyle={{
          padding: '12px',
        }}
        onClick={() => {
          if (item.description) {
            handleViewDescription(item.key, false);
          }
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Text strong style={{ fontSize: '13px' }}>
              {item.title}
            </Text>
            {item.description && (
              <InfoCircleOutlined
                style={{
                  fontSize: '14px',
                  flexShrink: 0,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleViewDescription(item.key, false);
                }}
              />
            )}
          </div>
          <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>
            {item.class_name}
          </Text>
          {preview && (
            <Text
              type="secondary"
              style={{
                fontSize: '12px',
                display: 'block',
                lineHeight: '1.4',
              }}
            >
              {preview}
            </Text>
          )}
        </Space>
      </Card>
    );
  };

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
            gap: '16px',
          }}
        >
          <Spin size="large" />
          <Text>{t('simSettings.loading')}</Text>
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={themeConfig}>
      <div
        style={{
          padding: '20px',
          minHeight: '100vh',
        }}
      >
        <Title level={2} style={{ marginBottom: '16px' }}>
          {t('simSettings.title')}
        </Title>

        <Alert
          message={t('simSettings.description')}
          description={t('simSettings.descriptionDetail')}
          type="info"
          showIcon
          style={{ marginBottom: '24px' }}
        />

        {saved && (
          <Alert
            message={t('simSettings.saved')}
            type="success"
            showIcon
            closable
            style={{ marginBottom: '16px' }}
            onClose={() => setSaved(false)}
          />
        )}

        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Agent Classes Selection */}
          <Card
            title={t('simSettings.agentClasses.title')}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary" style={{ fontSize: '13px', marginBottom: '8px' }}>
                {t('simSettings.agentClasses.description')}
              </Text>
              <div style={{ width: '100%', overflow: 'hidden' }}>
                <Transfer
                  dataSource={agentDataSource}
                  targetKeys={agentClassesList}
                  onChange={(keys) => setAgentClassesList(keys as string[])}
                  render={(item) => renderAgentItem(item as typeof agentDataSource[0])}
                  showSearch
                  filterOption={(inputValue, item) =>
                    item.title.toLowerCase().includes(inputValue.toLowerCase()) ||
                    item.class_name.toLowerCase().includes(inputValue.toLowerCase()) ||
                    (item.description || '').toLowerCase().includes(inputValue.toLowerCase())
                  }
                  titles={[
                    t('simSettings.agentClasses.available') || 'Available',
                    t('simSettings.agentClasses.selected') || 'Selected',
                  ]}
                  operations={[
                    t('simSettings.add') || 'Add',
                    t('simSettings.remove') || 'Remove',
                  ]}
                  listStyle={{
                    width: 'calc(50% - 80px)',
                    height: 400,
                  }}
                  style={{
                    width: '100%',
                  }}
                />
              </div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {t('simSettings.agentClasses.hint')}
              </Text>
            </Space>
          </Card>

          {/* Environment Modules Selection */}
          <Card
            title={t('simSettings.envModules.title')}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary" style={{ fontSize: '13px', marginBottom: '8px' }}>
                {t('simSettings.envModules.description')}
              </Text>
              <div style={{ width: '100%', overflow: 'hidden' }}>
                <Transfer
                  dataSource={envModuleDataSource}
                  targetKeys={envModulesList}
                  onChange={(keys) => setEnvModulesList(keys as string[])}
                  render={(item) => renderEnvModuleItem(item as typeof envModuleDataSource[0])}
                  showSearch
                  filterOption={(inputValue, item) =>
                    item.title.toLowerCase().includes(inputValue.toLowerCase()) ||
                    item.class_name.toLowerCase().includes(inputValue.toLowerCase()) ||
                    (item.description || '').toLowerCase().includes(inputValue.toLowerCase())
                  }
                  titles={[
                    t('simSettings.envModules.available') || 'Available',
                    t('simSettings.envModules.selected') || 'Selected',
                  ]}
                  operations={[
                    t('simSettings.add') || 'Add',
                    t('simSettings.remove') || 'Remove',
                  ]}
                  listStyle={{
                    width: 'calc(50% - 80px)',
                    height: 400,
                  }}
                  style={{
                    width: '100%',
                  }}
                />
              </div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {t('simSettings.envModules.hint')}
              </Text>
            </Space>
          </Card>

          {/* Action Buttons */}
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              size="large"
            >
              {t('simSettings.save')}
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleLoadDefaults}
              size="large"
            >
              {t('simSettings.loadDefaults')}
            </Button>
          </Space>

          {/* Info Card */}
          <Card
            style={{
              borderLeftWidth: '3px',
            }}
          >
            <Space direction="vertical" size="small">
              <Text strong>{t('simSettings.note.title')}</Text>
              <Text>
                {t('simSettings.note.text1')}
              </Text>
              <Text>
                {t('simSettings.note.text2')}
              </Text>
              <Text>
                {t('simSettings.note.text3')}
              </Text>
            </Space>
          </Card>
        </Space>

        {/* Description Modal */}
        <Modal
          title={currentDescription?.title || t('simSettings.descriptionModal.title')}
          open={descriptionModalVisible}
          onCancel={handleCloseDescriptionModal}
          footer={[
            <Button key="close" onClick={handleCloseDescriptionModal}>
              {t('simSettings.close') || 'Close'}
            </Button>,
          ]}
          width={800}
          style={{
            top: 20,
          }}
          styles={{
            body: {
              maxHeight: '70vh',
              overflow: 'auto',
              padding: '24px',
            },
          }}
        >
          {currentDescription?.content ? (
            <MarkdownRenderer
              content={currentDescription.content}
              isDark={isDark}
            />
          ) : (
            <Text type="secondary">{t('simSettings.descriptionModal.noDescription')}</Text>
          )}
        </Modal>
      </div>
    </ConfigProvider>
  );
};

