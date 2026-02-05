import * as React from 'react';
import { Badge, Button, Typography, Space, Drawer, List } from 'antd';
import { ClearOutlined, BugOutlined, HistoryOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

const { Text } = Typography;

interface HistoryItem {
  fileName: string;
  startTime?: string;
  displayName: string;
}

interface HeaderProps {
  // backendStatus: 后端健康检查状态和URL
  backendStatus: {
    connected: boolean;
    url?: string;
  };
  onClearChat: () => void; // 清除聊天回调
  showEvents: boolean; // 是否正在显示事件日志面板
  onToggleEvents: () => void; // 切换显示事件日志面板的回调
  histories: HistoryItem[]; // 历史记录列表
  onLoadHistory: (fileName: string) => void; // 加载历史记录回调
  onListHistories: () => void; // 获取历史记录列表回调
}

export const Header: React.FC<HeaderProps> = ({
  backendStatus,
  onClearChat,
  showEvents,
  onToggleEvents,
  histories,
  onLoadHistory,
  onListHistories
}: HeaderProps) => {
  const { t } = useTranslation();
  const [historyDrawerOpen, setHistoryDrawerOpen] = React.useState<boolean>(false);

  // 组件挂载时获取历史记录列表
  React.useEffect(() => {
    onListHistories();
  }, [onListHistories]);

  const handleOpenHistoryDrawer = () => {
    setHistoryDrawerOpen(true);
    // 打开抽屉时刷新历史记录列表
    onListHistories();
  };

  const handleCloseHistoryDrawer = () => {
    setHistoryDrawerOpen(false);
  };

  const handleHistoryItemClick = (fileName: string) => {
    onLoadHistory(fileName);
    setHistoryDrawerOpen(false);
  };

  return (
    <div
      style={{
        padding: '12px 16px',
        border: '1px solid var(--vscode-panel-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        backgroundColor: 'var(--vscode-editor-background)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Text strong style={{ fontSize: '13px', color: 'var(--vscode-foreground)' }}>
          {t('chat.appTitle')}
        </Text>
        <Badge
          status={backendStatus.connected ? 'success' : 'error'}
          text={
            <Text
              style={{
                fontSize: '11px',
                color: 'var(--vscode-descriptionForeground)',
              }}
            >
              {backendStatus.connected
                ? t('chat.connected')
                : backendStatus.url
                  ? t('chat.disconnectedWithUrl', { url: backendStatus.url })
                  : t('chat.disconnected')}
            </Text>
          }
        />
      </div>
      <Space>
        <Button
          type="text"
          size="small"
          icon={<HistoryOutlined />}
          onClick={handleOpenHistoryDrawer}
          style={{
            color: 'var(--vscode-foreground)',
          }}
          title="历史记录"
        >
          历史记录
        </Button>
        <Button
          type={showEvents ? "primary" : "text"}
          size="small"
          icon={<BugOutlined />}
          onClick={onToggleEvents}
          style={{
            color: showEvents ? undefined : 'var(--vscode-foreground)',
          }}
          title={t('chat.showEvents')}
        >
          {showEvents ? t('chat.hideEvents') : t('chat.events')}
        </Button>
        <Button
          type="text"
          size="small"
          icon={<ClearOutlined />}
          onClick={onClearChat}
          style={{
            color: 'var(--vscode-foreground)',
          }}
        >
          {t('chat.clear')}
        </Button>
      </Space>

      <Drawer
        title="历史记录"
        placement="right"
        onClose={handleCloseHistoryDrawer}
        open={historyDrawerOpen}
        width={400}
        styles={{
          body: {
            backgroundColor: 'var(--vscode-editor-background)',
            color: 'var(--vscode-editor-foreground)',
            padding: 0,
          },
          header: {
            backgroundColor: 'var(--vscode-editor-background)',
            borderBottom: '1px solid var(--vscode-panel-border)',
          },
        }}
      >
        {histories.length === 0 ? (
          <div
            style={{
              padding: '24px',
              textAlign: 'center',
              color: 'var(--vscode-descriptionForeground)',
            }}
          >
            暂无历史记录
          </div>
        ) : (
          <List
            dataSource={histories}
            renderItem={(item) => (
              <List.Item
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--vscode-panel-border)',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                }}
                onClick={() => handleHistoryItemClick(item.fileName)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--vscode-list-hoverBackground)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div style={{ width: '100%' }}>
                  <Text
                    style={{
                      color: 'var(--vscode-foreground)',
                      fontSize: '13px',
                      display: 'block',
                      marginBottom: '4px',
                    }}
                  >
                    {item.displayName}
                  </Text>
                  {item.startTime && (
                    <Text
                      type="secondary"
                      style={{
                        fontSize: '11px',
                        color: 'var(--vscode-descriptionForeground)',
                      }}
                    >
                      {new Date(item.startTime).toLocaleString('zh-CN')}
                    </Text>
                  )}
                </div>
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </div>
  );
};
