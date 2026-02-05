import * as React from 'react';
import { Layout, Input, Card, Typography, Spin, Alert, Empty, Space, Badge, Collapse } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ClassInfo, AvailableClasses, PrefillParams } from './types';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import '../i18n';

const { Content, Sider } = Layout;
const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Panel } = Collapse;

interface PrefillParamsAppProps {
  vscode: VSCodeAPI;
}

interface ClassItem {
  type: string;
  kind: 'env_module' | 'agent';
  info: ClassInfo;
  params: Record<string, any>;
}

export const PrefillParamsApp: React.FC<PrefillParamsAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const [classes, setClasses] = React.useState<ClassItem[]>([]);
  const [filteredClasses, setFilteredClasses] = React.useState<ClassItem[]>([]);
  const [selectedClass, setSelectedClass] = React.useState<ClassItem | null>(null);
  const [searchText, setSearchText] = React.useState<string>('');
  const [filterKind, setFilterKind] = React.useState<'env_module' | 'agent' | undefined>(undefined);
  const [isDark, setIsDark] = React.useState<boolean>(false);

  // 检测暗色主题
  React.useEffect(() => {
    const checkDarkMode = () => {
      setIsDark(
        document.body.classList.contains('vscode-dark') ||
        document.body.classList.contains('vscode-high-contrast')
      );
    };
    checkDarkMode();
    // 监听主题变化
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
          const filterKindFromMessage = message.filterKind as 'env_module' | 'agent' | undefined;

          // 更新过滤类型
          if (filterKindFromMessage !== undefined) {
            setFilterKind(filterKindFromMessage);
          }

          // 构建类列表
          const classItems: ClassItem[] = [];

          // 添加环境模块
          Object.entries(classesData.env_modules).forEach(([type, info]) => {
            classItems.push({
              type,
              kind: 'env_module',
              info,
              params: prefillParams.env_modules[type] || {},
            });
          });

          // 添加Agent类
          Object.entries(classesData.agents).forEach(([type, info]) => {
            classItems.push({
              type,
              kind: 'agent',
              info,
              params: prefillParams.agents[type] || {},
            });
          });

          setClasses(classItems);

          // 应用过滤
          let filtered = classItems;
          if (filterKindFromMessage) {
            filtered = classItems.filter(item => item.kind === filterKindFromMessage);
          }
          setFilteredClasses(filtered);

          setLoading(false);
          setError(null);
        } catch (e) {
          console.error('Error processing initial data:', e);
          setError(t('prefillParams.errorMessages.loadFailed'));
          setLoading(false);
        }
      } else if (message.command === 'setFilterKind') {
        // 更新过滤类型
        const newFilterKind = message.kind as 'env_module' | 'agent' | undefined;
        setFilterKind(newFilterKind);
        // 重新过滤
        let filtered = classes;
        if (newFilterKind) {
          filtered = classes.filter(item => item.kind === newFilterKind);
        }
        setFilteredClasses(filtered);
        // 如果当前选中的类不在过滤范围内，清除选择
        if (selectedClass && newFilterKind && selectedClass.kind !== newFilterKind) {
          setSelectedClass(null);
        }
      } else if (message.command === 'error') {
        setError(message.error || t('prefillParams.errorMessages.loadFailed'));
        setLoading(false);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [vscode]);

  // 搜索过滤
  React.useEffect(() => {
    let filtered = classes;

    // 先应用类型过滤
    if (filterKind) {
      filtered = filtered.filter(item => item.kind === filterKind);
    }

    // 再应用搜索过滤
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
  }, [searchText, classes, filterKind]);

  const handleRefresh = () => {
    setLoading(true);
    setError(null);
    vscode.postMessage({
      command: 'refresh',
    });
  };

  const handleClassSelect = (item: ClassItem) => {
    setSelectedClass(item);
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

  return (
    <Layout style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px', borderBottom: '1px solid #d9d9d9' }}>
        <Space style={{ width: '100%' }} direction="vertical" size="small">
          <Space>
            <Title level={5} style={{ margin: 0 }}>
              {t('prefillParams.title')}
            </Title>
            <ReloadOutlined
              onClick={handleRefresh}
              style={{ cursor: 'pointer', fontSize: '16px' }}
              title={t('prefillParams.refresh')}
            />
          </Space>
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
      <Layout style={{ flex: 1, overflow: 'hidden' }}>
        <Sider
          width={300}
          style={{
            background: '#fff',
            borderRight: '1px solid #d9d9d9',
            overflow: 'auto',
          }}
        >
          <div style={{ padding: '8px' }}>
            {filteredClasses.length === 0 ? (
              <Empty description={t('prefillParams.noClasses')} />
            ) : (
              <Collapse
                defaultActiveKey={
                  filterKind
                    ? filterKind === 'env_module'
                      ? ['env_modules']
                      : ['agents']
                    : ['env_modules', 'agents']
                }
                ghost
                style={{ background: 'transparent' }}
              >
                {/* 环境模块分组 */}
                {(!filterKind || filterKind === 'env_module') && (
                  <Panel
                    header={`${t('prefillParams.classInfo.envModule')} (${filteredClasses.filter(item => item.kind === 'env_module').length})`}
                    key="env_modules"
                    style={{ padding: 0 }}
                  >
                    {filteredClasses
                      .filter(item => item.kind === 'env_module')
                      .length === 0 ? (
                      <Empty description={t('prefillParams.noClasses')} />
                    ) : (
                      filteredClasses
                        .filter(item => item.kind === 'env_module')
                        .map((item) => (
                          <Card
                            key={`${item.kind}-${item.type}`}
                            size="small"
                            style={{
                              marginBottom: '8px',
                              cursor: 'pointer',
                              border:
                                selectedClass?.type === item.type &&
                                  selectedClass?.kind === item.kind
                                  ? '2px solid #1890ff'
                                  : '1px solid #d9d9d9',
                            }}
                            onClick={() => handleClassSelect(item)}
                          >
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
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
                              <Text type="secondary" style={{ fontSize: '12px' }}>
                                {item.info.class_name}
                              </Text>
                              {item.info.has_prefill && (
                                <Text type="success" style={{ fontSize: '12px' }}>
                                  {t('prefillParams.classInfo.hasPrefill')}
                                </Text>
                              )}
                            </Space>
                          </Card>
                        ))
                    )}
                  </Panel>
                )}

                {/* Agent分组 */}
                {(!filterKind || filterKind === 'agent') && (
                  <Panel
                    header={`${t('prefillParams.classInfo.agent')} (${filteredClasses.filter(item => item.kind === 'agent').length})`}
                    key="agents"
                    style={{ padding: 0 }}
                  >
                    {filteredClasses
                      .filter(item => item.kind === 'agent')
                      .length === 0 ? (
                      <Empty description={t('prefillParams.noClasses')} />
                    ) : (
                      filteredClasses
                        .filter(item => item.kind === 'agent')
                        .map((item) => (
                          <Card
                            key={`${item.kind}-${item.type}`}
                            size="small"
                            style={{
                              marginBottom: '8px',
                              cursor: 'pointer',
                              border:
                                selectedClass?.type === item.type &&
                                  selectedClass?.kind === item.kind
                                  ? '2px solid #1890ff'
                                  : '1px solid #d9d9d9',
                            }}
                            onClick={() => handleClassSelect(item)}
                          >
                            <Space direction="vertical" size="small" style={{ width: '100%' }}>
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
                              <Text type="secondary" style={{ fontSize: '12px' }}>
                                {item.info.class_name}
                              </Text>
                              {item.info.has_prefill && (
                                <Text type="success" style={{ fontSize: '12px' }}>
                                  {t('prefillParams.classInfo.hasPrefill')}
                                </Text>
                              )}
                            </Space>
                          </Card>
                        ))
                    )}
                  </Panel>
                )}
              </Collapse>
            )}
          </div>
        </Sider>
        <Content style={{ padding: '16px', overflow: 'auto' }}>
          {selectedClass ? (
            <div>
              <Title level={4}>
                {selectedClass.type}
                <Badge
                  status={selectedClass.info.has_prefill ? 'success' : 'default'}
                  style={{ marginLeft: '8px' }}
                />
              </Title>
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
        </Content>
      </Layout>
    </Layout>
  );
};
