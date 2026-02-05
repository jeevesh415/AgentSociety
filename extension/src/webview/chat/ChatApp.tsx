import * as React from 'react';
import { ConfigProvider, theme, Input, Button, Spin, Avatar, Typography } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, DownOutlined, UpOutlined, CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { Header } from './Header';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import type { VSCodeAPI, ExtensionMessage, ConversationProcess, SSEEvent, MessageSSEEvent, ToolSSEEvent, CompleteSSEEvent } from './types';

const { Text } = Typography;

// 常量定义
const HEALTH_CHECK_INTERVAL = 5000; // 5秒
const EVENT_LIST_MAX_HEIGHT = '300px';

// 样式常量
const ICON_COLOR_LINK = 'var(--vscode-textLink-foreground)';
const ICON_COLOR_ERROR = 'var(--vscode-errorForeground)';

const AVATAR_STYLE_BASE: React.CSSProperties = {
  flexShrink: 0,
};

const AVATAR_STYLE_USER: React.CSSProperties = {
  ...AVATAR_STYLE_BASE,
  backgroundColor: 'var(--vscode-button-background)',
};

const AVATAR_STYLE_ROBOT: React.CSSProperties = {
  ...AVATAR_STYLE_BASE,
  backgroundColor: ICON_COLOR_LINK,
};

const MESSAGE_CONTAINER_STYLE: React.CSSProperties = {
  flex: 1,
  padding: '12px 16px',
  borderRadius: '6px',
  border: '1px solid var(--vscode-panel-border)',
};

interface ChatAppProps {
  vscode: VSCodeAPI;
}

interface BackendStatus {
  connected: boolean;
  url?: string;
}

interface HistoryItem {
  fileName: string;
  startTime?: string;
  displayName: string;
}

export const ChatApp: React.FC<ChatAppProps> = ({ vscode }: ChatAppProps) => {
  const { t } = useTranslation();
  // conversations: 存储所有对话的处理过程和结果
  const [conversations, setConversations] = React.useState<ConversationProcess[]>([]);
  // events: 存储所有从插件后端接收到的原始事件，用于调试日志
  const [events, setEvents] = React.useState<ExtensionMessage[]>([]);
  // showEvents: 是否显示事件日志面板
  const [showEvents, setShowEvents] = React.useState<boolean>(false);
  // backendStatus: 后端服务的连接状态
  const [backendStatus, setBackendStatus] = React.useState<BackendStatus>({
    connected: false,
  });
  const [loading, setLoading] = React.useState<boolean>(false);
  const [inputValue, setInputValue] = React.useState<string>('');
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const messagesContainerRef = React.useRef<HTMLDivElement>(null);
  // 当前正在处理的对话ID
  const [currentConversationId, setCurrentConversationId] = React.useState<string | null>(null);
  // 历史记录列表
  const [histories, setHistories] = React.useState<HistoryItem[]>([]);
  const [checkingHealth, setCheckingHealth] = React.useState<boolean>(false);
  // 用于跟踪上一次的conversations状态，判断是否需要滚动
  const prevConversationsRef = React.useRef<{
    length: number;
    eventCounts: Map<string, number>;
  }>({ length: 0, eventCounts: new Map() });

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 只在新增对话或新增事件时滚动，展开/收起事件时不滚动
  React.useEffect(() => {
    const prev = prevConversationsRef.current;
    const currentLength = conversations.length;
    const currentEventCounts = new Map<string, number>();

    conversations.forEach(conv => {
      currentEventCounts.set(conv.id, conv.events.length);
    });

    // 检查是否有新增对话
    const hasNewConversation = currentLength > prev.length;

    // 检查是否有新增事件（排除isExpanded变化的情况）
    let hasNewEvents = false;
    if (currentLength === prev.length) {
      // 对话数量没变，检查事件数量是否增加
      for (const conv of conversations) {
        const prevCount = prev.eventCounts.get(conv.id) || 0;
        const currentCount = conv.events.length;
        if (currentCount > prevCount) {
          hasNewEvents = true;
          break;
        }
      }
    } else {
      // 对话数量变化，可能是新增对话，需要滚动
      hasNewEvents = true;
    }

    // 只在新增对话或新增事件时滚动
    if (hasNewConversation || hasNewEvents) {
      scrollToBottom();
    }

    // 更新ref
    prevConversationsRef.current = {
      length: currentLength,
      eventCounts: currentEventCounts,
    };
  }, [conversations]);

  const handleListHistories = React.useCallback((): void => {
    vscode.postMessage({
      command: 'listHistories',
    });
  }, [vscode]);

  // 初始化时请求历史记录列表
  React.useEffect(() => {
    handleListHistories();
  }, [handleListHistories]);

  React.useEffect(() => {
    // 监听来自扩展的消息
    const handleMessage = (event: MessageEvent<ExtensionMessage>) => {
      const message = event.data;

      // 记录所有接收到的事件到日志列表中（排除complete事件）
      if (!(message.command === 'sseEvent' && message.event?.type === 'complete')) {
        setEvents(prev => [...prev, { ...message, timestamp: Date.now() } as ExtensionMessage & { timestamp: number }]);
      }

      switch (message.command) {
        case 'sseEvent':
          if (message.event) {
            handleSSEEvent(message.event);
          }
          break;

        case 'clearMessages':
          setConversations([]);
          setCurrentConversationId(null);
          setLoading(false);
          break;

        case 'backendStatus':
          setBackendStatus({
            connected: message.connected ?? false,
            url: message.url,
          });
          setCheckingHealth(false);
          break;

        case 'historyLoaded':
          // 历史记录已加载，恢复对话
          if (message.messages && Array.isArray(message.messages)) {
            // 将历史记录转换为conversations格式
            // 历史记录中的消息格式：{ role: 'user' | 'assistant', content: string }
            const loadedConversations: ConversationProcess[] = [];
            let currentUserMessage: string | null = null;
            let currentFinalContent: string | null = null;
            let currentUserMessageIndex: number = -1; // 跟踪当前用户消息在原始消息数组中的索引

            // 创建SSE事件映射：userMessageIndex -> events
            // userMessageIndex: 用户消息在messages数组中的索引位置，用于关联该消息对应的所有SSE事件
            const sseEventsMap = new Map<number, Array<{ event: SSEEvent; timestamp: number }>>();
            if (message.sseEvents && Array.isArray(message.sseEvents)) {
              message.sseEvents.forEach((item: { userMessageIndex?: number; events?: Array<{ event: SSEEvent; timestamp: number }> }) => {
                if (item.userMessageIndex !== undefined && item.events && Array.isArray(item.events)) {
                  // item.userMessageIndex 是用户消息在messages数组中的索引
                  sseEventsMap.set(item.userMessageIndex, item.events);
                }
              });
            }

            message.messages.forEach((msg: { role: 'user' | 'assistant'; content?: string }, index: number) => {
              if (msg.role === 'user') {
                // 如果之前有未完成的对话，先保存它
                if (currentUserMessage !== null) {
                  // 获取该用户消息对应的SSE事件
                  const events = sseEventsMap.get(currentUserMessageIndex) || [];
                  loadedConversations.push({
                    id: `conv-hist-${index}`,
                    userMessage: currentUserMessage,
                    events: events, // 恢复SSE事件
                    isComplete: currentFinalContent !== null,
                    finalContent: currentFinalContent,
                    isExpanded: false,
                  });
                }
                // 开始新的对话
                currentUserMessage = msg.content || '';
                currentUserMessageIndex = index; // 记录用户消息的索引
                currentFinalContent = null;
              } else if (msg.role === 'assistant') {
                // 这是assistant的回复，作为finalContent
                currentFinalContent = msg.content || '';
              }
            });

            // 保存最后一个对话
            if (currentUserMessage !== null) {
              // 获取最后一个用户消息对应的SSE事件
              const events = sseEventsMap.get(currentUserMessageIndex) || [];
              loadedConversations.push({
                id: `conv-hist-${message.messages.length}`,
                userMessage: currentUserMessage,
                events: events, // 恢复SSE事件
                isComplete: currentFinalContent !== null,
                finalContent: currentFinalContent,
                isExpanded: false,
              });
            }

            setConversations(loadedConversations);
            setLoading(false);
            setCurrentConversationId(null);
          }
          break;

        case 'historyList':
          // 更新历史记录列表
          if (message.histories) {
            setHistories(message.histories);
          }
          break;

        case 'historyLoadError':
          // 历史记录加载失败
          console.error('Failed to load history:', message.error);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const handleCheckHealth = React.useCallback((): void => {
    setCheckingHealth(true);
    vscode.postMessage({
      command: 'checkHealth',
    });
  }, [vscode]);

  // 定期检查后端健康状态（每5秒检查一次）
  React.useEffect(() => {
    // 立即检查一次
    handleCheckHealth();

    // 设置定时器，每5秒检查一次
    const intervalId = setInterval(() => {
      handleCheckHealth();
    }, HEALTH_CHECK_INTERVAL);

    // 清理定时器
    return () => {
      clearInterval(intervalId);
    };
  }, [handleCheckHealth]); // 依赖handleCheckHealth

  const handleSSEEvent = React.useCallback((event: SSEEvent) => {
    setConversations(prev => {
      const updated = [...prev];

      // 找到最后一个未完成的对话
      let currentIndex = -1;
      for (let i = updated.length - 1; i >= 0; i--) {
        if (!updated[i].isComplete) {
          currentIndex = i;
          break;
        }
      }

      if (currentIndex === -1) {
        // 如果没有找到未完成的对话，可能是事件顺序问题，跳过
        return prev;
      }

      const conversation = updated[currentIndex];

      // 处理complete事件
      if (event.type === 'complete') {
        const completeEvent = event as CompleteSSEEvent;
        conversation.isComplete = true;
        conversation.finalContent = completeEvent.content;
        conversation.isExpanded = false; // 完成后默认收起
        setLoading(false);
        setCurrentConversationId(null);
      } else {
        // 添加事件到处理过程
        conversation.events.push({
          event: event,
          timestamp: Date.now(),
        });

        // 如果是错误事件，也停止loading
        if (event.type === 'message' && (event as MessageSSEEvent).is_error) {
          setLoading(false);
          setCurrentConversationId(null);
        }
      }

      updated[currentIndex] = { ...conversation };
      return updated;
    });
  }, []);

  const handleSendMessage = async (): Promise<void> => {
    if (!inputValue.trim() || loading) {
      return;
    }

    const conversationId = `conv-${Date.now()}`;
    setCurrentConversationId(conversationId);
    setLoading(true);

    // 创建新的对话
    const newConversation: ConversationProcess = {
      id: conversationId,
      userMessage: inputValue.trim(),
      events: [],
      isComplete: false,
      finalContent: null,
      isExpanded: true,
    };

    setConversations(prev => [...prev, newConversation]);
    setInputValue('');

    vscode.postMessage({
      command: 'sendMessage',
      text: inputValue.trim(),
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleClearChat = (): void => {
    vscode.postMessage({
      command: 'clearChat',
    });
  };

  const handleLoadHistory = React.useCallback((fileName: string): void => {
    vscode.postMessage({
      command: 'loadHistory',
      historyFileName: fileName,
    });
  }, [vscode]);

  const toggleConversationExpanded = (conversationId: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === conversationId
          ? { ...conv, isExpanded: !conv.isExpanded }
          : conv
      )
    );
  };


  // 统一渲染事件的通用函数
  const renderEvent = (
    index: number,
    options: {
      icon: React.ReactNode;
      content: string | null | undefined;
      renderContent: (content: string | null | undefined) => React.ReactNode;
    }
  ) => {
    const { icon, content, renderContent } = options;

    return (
      <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0' }}>
        {icon}
        {renderContent(content || null)}
      </div>
    );
  };

  const renderEventItem = (event: SSEEvent, index: number, totalEvents: number, isComplete: boolean) => {
    const isLastEvent = index === totalEvents - 1;
    const isInProgress = !isComplete && isLastEvent;

    if (event.type === 'message') {
      const msgEvent = event as MessageSSEEvent;

      if (msgEvent.is_thinking) {
        // 思考事件：如果是最后一个且未完成，显示spin，否则显示已完成
        const icon = isInProgress ? (
          <LoadingOutlined style={{ color: ICON_COLOR_LINK }} />
        ) : (
          <CheckCircleOutlined style={{ color: ICON_COLOR_LINK }} />
        );
        return renderEvent(index, {
          icon,
          content: msgEvent.content,
          renderContent: (content) => (
            <Text type="secondary" style={{ fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {content || ''}
            </Text>
          ),
        });
      } else if (msgEvent.is_error) {
        // 错误事件
        const icon = <span style={{ color: ICON_COLOR_ERROR }}>❌</span>;
        return renderEvent(index, {
          icon,
          content: msgEvent.content,
          renderContent: (content) => (
            <Text type="secondary" style={{ fontSize: '12px', color: 'var(--vscode-errorForeground)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {content || ''}
            </Text>
          ),
        });
      } else {
        // 普通消息事件
        const icon = <CheckCircleOutlined style={{ color: ICON_COLOR_LINK }} />;
        return renderEvent(index, {
          icon,
          content: msgEvent.content,
          renderContent: (content) => (
            <Text type="secondary" style={{ fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {content || ''}
            </Text>
          ),
        });
      }
    } else if (event.type === 'tool') {
      const toolEvent = event as ToolSSEEvent;

      // 根据状态和是否是最后一个事件决定图标
      let statusIcon;
      if (toolEvent.status === 'start' || toolEvent.status === 'progress') {
        // 开始或执行中：如果是最后一个且未完成，显示spin，否则显示已完成
        statusIcon = isInProgress ? (
          <LoadingOutlined style={{ color: ICON_COLOR_LINK }} />
        ) : (
          <CheckCircleOutlined style={{ color: ICON_COLOR_LINK }} />
        );
      } else if (toolEvent.status === 'success') {
        statusIcon = <CheckCircleOutlined style={{ color: ICON_COLOR_LINK }} />;
      } else {
        statusIcon = <span style={{ color: ICON_COLOR_ERROR }}>❌</span>;
      }

      const statusText = {
        start: isInProgress ? '开始执行' : '已开始',
        progress: isInProgress ? '执行中' : '已执行',
        success: '执行成功',
        error: '执行失败',
      }[toolEvent.status];

      // 使用统一的渲染函数处理工具事件
      return renderEvent(index, {
        icon: statusIcon,
        content: toolEvent.content,
        renderContent: (content) => {
          if (content) {
            return (
              <Text type="secondary" style={{ fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                <strong>{toolEvent.tool_name}</strong>: {statusText} - {content}
              </Text>
            );
          } else {
            return (
              <Text type="secondary" style={{ fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                <strong>{toolEvent.tool_name}</strong>: {statusText}
              </Text>
            );
          }
        },
      });
    }
    return null;
  };

  // 适配 VSCode 主题
  const isDark = React.useMemo<boolean>(() =>
    document.body.classList.contains('vscode-dark') ||
    document.body.classList.contains('vscode-high-contrast'),
    []
  );

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorBgContainer: 'var(--vscode-editor-background)',
          colorText: 'var(--vscode-editor-foreground)',
          colorBorder: 'var(--vscode-panel-border)',
          borderRadius: 6,
          colorPrimary: 'var(--vscode-button-background)',
          colorTextSecondary: 'var(--vscode-descriptionForeground)',
        },
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          backgroundColor: 'var(--vscode-editor-background)',
          color: 'var(--vscode-editor-foreground)',
        }}
      >
        <Header
          backendStatus={backendStatus}
          onClearChat={handleClearChat}
          showEvents={showEvents}
          onToggleEvents={() => setShowEvents(!showEvents)}
          histories={histories}
          onLoadHistory={handleLoadHistory}
          onListHistories={handleListHistories}
        />

        {showEvents && (
          <div
            style={{
              padding: '8px 16px',
              backgroundColor: 'var(--vscode-debugConsole-background, rgba(0,0,0,0.1))',
              borderBottom: '1px solid var(--vscode-panel-border)',
              maxHeight: '200px',
              overflow: 'auto',
              fontSize: '11px',
              fontFamily: 'var(--vscode-editor-font-family, monospace)',
            }}
          >
            <div style={{ fontWeight: 'bold', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
              <span>{t('chat.eventLogWithCount', { count: events.length })}</span>
              <Button size="small" type="text" onClick={() => setEvents([])} style={{ fontSize: '10px', height: 'auto', padding: '0 4px' }}>{t('chat.clearLog')}</Button>
            </div>
            {events.slice().reverse().map((event, i) => (
              <div key={i} style={{ marginBottom: '2px', borderBottom: '1px solid rgba(128,128,128,0.1)', paddingBottom: '2px' }}>
                <span style={{ opacity: 0.5 }}>{new Date((event as any).timestamp).toLocaleTimeString()}</span>{' '}
                <span style={{ color: 'var(--vscode-symbolIcon-functionForeground)' }}>[{event.command}]</span>{' '}
                {event.command === 'sseEvent' && event.event ? (
                  <span style={{ opacity: 0.8 }}>
                    {JSON.stringify(event.event)}
                  </span>
                ) : (
                  <span style={{ opacity: 0.8 }}>
                    {JSON.stringify(Object.fromEntries(Object.entries(event).filter(([k]) => k !== 'command' && k !== 'timestamp')))}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 消息列表区域 */}
        <div
          ref={messagesContainerRef}
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          {conversations.length === 0 && (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--vscode-descriptionForeground)',
                fontSize: '13px',
              }}
            >
              {t('chat.startChat')}
            </div>
          )}

          {conversations.map((conversation) => (
            <div key={conversation.id} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* 用户消息 */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'row-reverse',
                  gap: '12px',
                  alignItems: 'flex-start',
                }}
              >
                <Avatar
                  icon={<UserOutlined />}
                  style={AVATAR_STYLE_USER}
                />
                <div
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: '6px',
                    backgroundColor: 'var(--vscode-input-background)',
                    border: '1px solid var(--vscode-panel-border)',
                    maxWidth: '80%',
                  }}
                >
                  <div style={{ fontSize: '13px', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
                    {conversation.userMessage}
                  </div>
                </div>
              </div>

              {/* 处理过程Block */}
              {(() => {
                // 过滤掉complete事件
                const filteredEvents = conversation.events.filter(item => item.event.type !== 'complete');
                if (filteredEvents.length === 0) {
                  return null;
                }
                return (
                  <div
                    style={{
                      border: '1px solid var(--vscode-panel-border)',
                      borderRadius: '6px',
                      backgroundColor: 'var(--vscode-editor-background)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      onClick={() => toggleConversationExpanded(conversation.id)}
                      style={{
                        padding: '8px 12px',
                        backgroundColor: conversation.isComplete
                          ? 'var(--vscode-editor-background)'
                          : 'var(--vscode-input-background)',
                        borderBottom: conversation.isExpanded ? '1px solid var(--vscode-panel-border)' : 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        userSelect: 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {conversation.isComplete ? (
                          <CheckCircleOutlined style={{ color: ICON_COLOR_LINK }} />
                        ) : (
                          <LoadingOutlined style={{ color: ICON_COLOR_LINK }} />
                        )}
                        <Text style={{ fontSize: '12px', fontWeight: 500 }}>
                          {conversation.isComplete ? '处理完成' : '处理中...'}
                        </Text>
                        <Text type="secondary" style={{ fontSize: '11px' }}>
                          ({filteredEvents.length} 个事件)
                        </Text>
                      </div>
                      {conversation.isExpanded ? <UpOutlined /> : <DownOutlined />}
                    </div>
                    {conversation.isExpanded && (
                      <div
                        style={{
                          padding: '12px',
                          maxHeight: EVENT_LIST_MAX_HEIGHT,
                          overflow: 'auto',
                        }}
                      >
                        {filteredEvents.map((item, index) =>
                          renderEventItem(item.event, index, filteredEvents.length, conversation.isComplete)
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* 最终结果Block */}
              {conversation.isComplete && conversation.finalContent && (
                <div
                  style={{
                    display: 'flex',
                    gap: '12px',
                    alignItems: 'flex-start',
                  }}
                >
                  <Avatar
                    icon={<RobotOutlined />}
                    style={AVATAR_STYLE_ROBOT}
                  />
                  <div
                    style={{
                      ...MESSAGE_CONTAINER_STYLE,
                      backgroundColor: 'var(--vscode-editor-background)',
                    }}
                  >
                    <MarkdownRenderer
                      content={conversation.finalContent}
                      isDark={isDark}
                      customComponents={{
                        a: (props: any) => {
                          const href = props.href;
                          if (href && (href.startsWith('/') || href.includes('\\'))) {
                            return (
                              <a
                                {...props}
                                onClick={(e: React.MouseEvent) => {
                                  e.preventDefault();
                                  vscode.postMessage({
                                    command: 'openFile',
                                    filePath: href,
                                  });
                                }}
                                style={{
                                  color: 'var(--vscode-textLink-foreground)',
                                  cursor: 'pointer',
                                  textDecoration: 'underline',
                                }}
                              />
                            );
                          }
                          return <a {...props} />;
                        },
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}

          {loading && conversations.length > 0 && conversations[conversations.length - 1]?.events.length === 0 && (
            <div
              style={{
                display: 'flex',
                gap: '12px',
                alignItems: 'flex-start',
              }}
            >
              <Avatar
                icon={<RobotOutlined />}
                style={{
                  backgroundColor: 'var(--vscode-textLink-foreground)',
                  flexShrink: 0,
                }}
              />
              <div
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--vscode-editor-background)',
                  border: '1px solid var(--vscode-panel-border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <Spin size="small" />
                <span style={{ color: 'var(--vscode-descriptionForeground)' }}>
                  {t('chat.generating')}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--vscode-panel-border)',
            backgroundColor: 'var(--vscode-editor-background)',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-end',
            }}
          >
            <Input.TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={t('chat.placeholder')}
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={loading}
              style={{
                backgroundColor: 'var(--vscode-input-background)',
                borderColor: 'var(--vscode-input-border)',
                color: 'var(--vscode-input-foreground)',
                fontSize: '13px',
                resize: 'none',
              }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || loading}
              style={{
                backgroundColor: 'var(--vscode-button-background)',
                borderColor: 'var(--vscode-button-background)',
                color: 'var(--vscode-button-foreground)',
                flexShrink: 0,
                height: '32px',
              }}
            >
              {t('chat.send')}
            </Button>
          </div>
        </div>
      </div>
    </ConfigProvider>
  );
};
