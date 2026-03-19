import * as React from 'react';
import { Input, Card, Typography, Spin, Alert, Empty, Space, Badge, Tabs, Tag, Button } from 'antd';
import { SearchOutlined, ReloadOutlined, PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ClassInfo, AvailableClasses, PrefillParams } from './types';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import '../i18n';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

interface PrefillParamsAppProps {
  vscode: VSCodeAPI;
}

interface ClassItem {
  type: string;
  kind: 'env_module' | 'agent';
  info: ClassInfo;
  params: Record<string, any>;
}

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export const PrefillParamsApp: React.FC<PrefillParamsAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const [classes, setClasses] = React.useState<ClassItem[]>([]);
  const [filteredClasses, setFilteredClasses] = React.useState<ClassItem[]>([]);
  const [selectedClass, setSelectedClass] = React.useState<ClassItem | null>(null);
  const [searchText, setSearchText] = React.useState<string>('');
  const [activeTab, setActiveTab] = React.useState<'env_module' | 'agent'>('env_module');
  const [isDark, setIsDark] = React.useState<boolean>(false);

  // 为每个模块维护测试状态，key 为 `${kind}-${type}`
  const [testStatuses, setTestStatuses] = React.useState<Record<string, TestStatus>>({});
  const [testResults, setTestResults] = React.useState<Record<string, string>>({});

  // 检测暗色主题
  React.useEffect(() => {
    const checkDarkMode = () => {
      setIsDark(
        document.body.classList.contains('vscode-dark') ||
        document.body.classList.contains('vscode-high-contrast')
      );
    };
    checkDarkMode();
    const observer = new MutationObserver(checkDarkMode);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class'],
    });
    return () => observer.disconnect();
  }, []);

  // 组件挂载时请求数据
  React.useEffect(() => {
    vscode.postMessage({
      command: 'requestData',
    });
  }, [vscode]);

  // 监听来自扩展的消息
  React.useEffect(() => {
    const handleMessage = (event: MessageEvent<any>) => {
      const message = event.data;

      if (message.command === 'initialData') {
        try {
          const classesData: AvailableClasses = message.classes;
          const prefillParams: PrefillParams = message.prefillParams;

          const classItems: ClassItem[] = [];

          Object.entries(classesData.env_modules).forEach(([type, info]) => {
            classItems.push({
              type,
              kind: 'env_module',
              info,
              params: prefillParams.env_modules[type] || {},
            });
          });

          Object.entries(classesData.agents).forEach(([type, info]) => {
            classItems.push({
              type,
              kind: 'agent',
              info,
              params: prefillParams.agents[type] || {},
            });
          });

          setClasses(classItems);
          setLoading(false);
          setError(null);
        } catch (e) {
          console.error('Error processing initial data:', e);
          setError(t('prefillParams.errorMessages.loadFailed'));
          setLoading(false);
          // 清除旧数据，防止在错误状态下显示旧内容
          setClasses([]);
          setFilteredClasses([]);
          setSelectedClass(null);
        }
      } else if (message.command === 'error') {
        setError(message.error || t('prefillParams.errorMessages.loadFailed'));
        setLoading(false);
        // 清除旧数据，防止在错误状态下显示旧内容
        setClasses([]);
        setFilteredClasses([]);
        setSelectedClass(null);
      } else if (message.command === 'testResult') {
        // 处理测试结果
        const moduleKey = message.moduleKey;
        if (moduleKey) {
          setTestStatuses(prev => ({
            ...prev,
            [moduleKey]: message.success ? 'success' : 'error',
          }));
          setTestResults(prev => ({
            ...prev,
            [moduleKey]: message.output || message.error || '',
          }));
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [vscode, t]);

  // 搜索过滤和Tab切换
  React.useEffect(() => {
    let filtered = classes;

    filtered = filtered.filter(item => item.kind === activeTab);

    if (searchText.trim()) {
      const lowerSearch = searchText.toLowerCase();
      filtered = filtered.filter((item) => {
        return (
          item.type.toLowerCase().includes(lowerSearch) ||
          item.info.class_name.toLowerCase().includes(lowerSearch) ||
          item.info.description.toLowerCase().includes(lowerSearch)
        );
      });
    }

    setFilteredClasses(filtered);

    if (selectedClass && selectedClass.kind !== activeTab) {
      setSelectedClass(null);
    }
  }, [searchText, classes, activeTab, selectedClass]);

  const handleRefresh = () => {
    setLoading(true);
    setError(null);
    // 清除旧数据，防止在错误状态下显示旧内容
    setClasses([]);
    setFilteredClasses([]);
    setSelectedClass(null);
    vscode.postMessage({
      command: 'refresh',
    });
  };

  const handleClassSelect = (item: ClassItem) => {
    setSelectedClass(item);
  };

  const handleTestModule = (item: ClassItem) => {
    const key = `${item.kind}-${item.type}`;
    setTestStatuses(prev => ({ ...prev, [key]: 'testing' }));
    setTestResults(prev => ({ ...prev, [key]: '' }));

    vscode.postMessage({
      command: 'testCustomModule',
      moduleKey: key,
      moduleType: item.kind,
      moduleTypeValue: item.type,
      moduleClassName: item.info.class_name,
    });
  };

  const getTestIcon = (status: TestStatus) => {
    switch (status) {
      case 'testing':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: '16px' }}>
          <Text>{t('prefillParams.loading')}</Text>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <Alert
          message={t('prefillParams.error')}
          description={error}
          type="error"
          showIcon
          action={
            <ReloadOutlined
              onClick={handleRefresh}
              style={{ cursor: 'pointer', fontSize: '16px' }}
            />
          }
        />
      </div>
    );
  }

  const customCount = classes.filter(c => c.info.is_custom).length;
  const builtinCount = classes.length - customCount;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px', borderBottom: '1px solid #d9d9d9', flexShrink: 0 }}>
        <Space style={{ width: '100%' }} direction="vertical" size="small">
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Title level={5} style={{ margin: 0 }}>
              {t('prefillParams.groupTitle')}
            </Title>
            <ReloadOutlined
              onClick={handleRefresh}
              style={{ cursor: 'pointer', fontSize: '16px' }}
              title={t('prefillParams.refresh')}
            />
          </Space>

          <Space style={{ width: '100%', justifyContent: 'space-between', fontSize: '12px', color: '#888' }}>
            <Space split={<span>|</span>}>
              <span>{t('prefillParams.classInfo.builtin')}: {builtinCount}</span>
              <span>{t('prefillParams.classInfo.custom')}: {customCount}</span>
            </Space>
          </Space>

          <Tabs
            activeKey={activeTab}
            onChange={(key) => {
              setActiveTab(key as 'env_module' | 'agent');
              setSelectedClass(null);
            }}
            style={{ marginBottom: 0 }}
            items={[
              {
                key: 'env_module',
                label: `${t('prefillParams.classInfo.envModule')} (${classes.filter(c => c.kind === 'env_module').length})`,
              },
              {
                key: 'agent',
                label: `${t('prefillParams.classInfo.agent')} (${classes.filter(c => c.kind === 'agent').length})`,
              },
            ]}
          />
          <Search
            placeholder={t('prefillParams.searchPlaceholder')}
            allowClear
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: '100%' }}
          />
        </Space>
      </div>
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div
          style={{
            width: '340px',
            background: '#fff',
            borderRight: '1px solid #d9d9d9',
            overflowY: 'auto',
            flexShrink: 0,
          }}
        >
          <div style={{ padding: '8px' }}>
            {filteredClasses.length === 0 ? (
              <Empty description={t('prefillParams.noClasses')} style={{ marginTop: '40px' }} />
            ) : (
              filteredClasses.map((item) => {
                const key = `${item.kind}-${item.type}`;
                const testStatus = testStatuses[key] || 'idle';
                const testResult = testResults[key];
                const isCustom = item.info.is_custom;

                return (
                  <Card
                    key={key}
                    size="small"
                    style={{
                      marginBottom: '8px',
                      cursor: 'pointer',
                      border:
                        selectedClass?.type === item.type &&
                          selectedClass?.kind === item.kind
                          ? '2px solid #1890ff'
                          : '1px solid #d9d9d9',
                      backgroundColor: isCustom ? '#fafafa' : '#fff',
                    }}
                    onClick={() => handleClassSelect(item)}
                    hoverable
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Space>
                          <Badge
                            status={item.info.has_prefill ? 'success' : 'default'}
                            text={
                            <Text strong>
                              {item.type}
                            </Text>
                          }
                          />
                        </Space>
                        <Tag color={isCustom ? 'blue' : 'default'}>
                          {isCustom
                            ? t('prefillParams.classInfo.custom')
                            : t('prefillParams.classInfo.builtin')}
                        </Tag>
                      </Space>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {item.info.class_name}
                      </Text>

                      {/* 自定义模块显示测试按钮和状态 */}
                      {isCustom && (
                        <Space style={{ width: '100%' }} size="small">
                          <Button
                            size="small"
                            icon={<PlayCircleOutlined />}
                            loading={testStatus === 'testing'}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTestModule(item);
                            }}
                          >
                            {t('prefillParams.classInfo.test')}
                          </Button>
                          {getTestIcon(testStatus)}
                        </Space>
                      )}

                      {testStatus !== 'idle' && testResult && (
                        <Alert
                          message={testStatus === 'success' ? t('prefillParams.test.success') : t('prefillParams.test.failed')}
                          description={
                            <Text
                              style={{
                                fontSize: '12px',
                                display: 'block',
                                maxHeight: '60px',
                                overflow: 'auto',
                                whiteSpace: 'pre-wrap'
                              }}
                            >
                              {testResult}
                            </Text>
                          }
                          type={testStatus === 'success' ? 'success' : 'error'}
                          showIcon
                          style={{ padding: '4px 8px', fontSize: '12px' }}
                        />
                      )}

                      {item.info.has_prefill && (
                        <Text type="success" style={{ fontSize: '12px' }}>
                          {t('prefillParams.classInfo.hasPrefill')}
                        </Text>
                      )}
                    </Space>
                  </Card>
                );
              })
            )}
          </div>
        </div>
        <div
          style={{
            flex: 1,
            padding: '16px',
            overflowY: 'auto',
            minWidth: 0,
          }}
        >
          {selectedClass ? (
            <div>
              <Space style={{ marginBottom: '8px' }}>
                <Title level={4} style={{ margin: 0 }}>
                  {selectedClass.type}
                </Title>
                <Badge
                  status={selectedClass.info.has_prefill ? 'success' : 'default'}
                />
                <Tag color={selectedClass.info.is_custom ? 'blue' : 'default'}>
                  {selectedClass.info.is_custom
                    ? t('prefillParams.classInfo.custom')
                    : t('prefillParams.classInfo.builtin')}
                </Tag>
              </Space>
              <Paragraph>
                <Text strong>{t('prefillParams.classInfo.className')}: </Text>
                <Text code>{selectedClass.info.class_name}</Text>
              </Paragraph>
              <Paragraph>
                <Text strong>{t('prefillParams.classInfo.kind')}: </Text>
                <Text>
                  {selectedClass.kind === 'env_module'
                    ? t('prefillParams.classInfo.envModule')
                    : t('prefillParams.classInfo.agent')}
                </Text>
              </Paragraph>
              <div style={{ marginTop: '16px' }}>
                <Text strong>{t('prefillParams.classInfo.description')}: </Text>
                <div style={{ marginTop: '8px' }}>
                  <MarkdownRenderer
                    content={selectedClass.info.description}
                    isDark={isDark}
                  />
                </div>
              </div>
              <div style={{ marginTop: '24px' }}>
                <Title level={5}>{t('prefillParams.classInfo.prefillParams')}</Title>
                {Object.keys(selectedClass.params).length === 0 ? (
                  <Alert
                    message={t('prefillParams.classInfo.noPrefillParams')}
                    type="info"
                    showIcon
                  />
                ) : (
                  <Card>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify(selectedClass.params, null, 2)}
                    </pre>
                  </Card>
                )}
              </div>
            </div>
          ) : (
            <Empty
              description={t('prefillParams.selectClass')}
              style={{ marginTop: '100px' }}
            />
          )}
        </div>
      </div>
    </div>
  );
};
