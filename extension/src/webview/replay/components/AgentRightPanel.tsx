/**
 * 右侧对话/社交/指标面板
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, Flex, Typography, Avatar, Select, Table, Pagination, Button, Spin, Modal, Divider, List } from 'antd';
import { SmileOutlined, GlobalOutlined, UserOutlined, DatabaseOutlined, ReloadOutlined, TableOutlined, MessageOutlined, TeamOutlined, CloseOutlined, FileTextOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import {
  DialogType,
  AgentDialog,
  SocialPost,
  SocialComment,
  SocialDirectMessage,
  SocialGroupMessage,
  SocialNetwork,
  SocialUser,
} from '../types';
import dayjs from 'dayjs';

const { Option } = Select;

const DatabaseTab: React.FC = () => {
  const { t } = useTranslation();
  const { state, sendMessage } = useReplay();
  const { dbTables, dbTableContent, loading } = state;
  const [selectedTable, setSelectedTable] = React.useState<string | null>(null);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [isModalVisible, setIsModalVisible] = React.useState(false);
  const pageSize = 20;

  // Fetch tables on mount
  React.useEffect(() => {
    sendMessage({ command: 'fetchDbTables' });
  }, [sendMessage]);

  const handleTableChange = (value: string) => {
    setSelectedTable(value);
    setCurrentPage(1);
    sendMessage({ command: 'fetchDbTableContent', tableName: value, page: 1, pageSize });
    setIsModalVisible(true);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    if (selectedTable) {
      sendMessage({ command: 'fetchDbTableContent', tableName: selectedTable, page, pageSize });
    }
  };

  const handleRefresh = () => {
    sendMessage({ command: 'fetchDbTables' });
    if (selectedTable) {
      sendMessage({ command: 'fetchDbTableContent', tableName: selectedTable, page: currentPage, pageSize });
    }
  };

  const showModal = () => {
    if (selectedTable) {
      setIsModalVisible(true);
    }
  };

  const handleCancel = () => {
    setIsModalVisible(false);
  };

  const columns = React.useMemo(() => {
    if (!dbTableContent || !dbTableContent.columns) return [];
    return dbTableContent.columns.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      render: (text: any) => {
        if (typeof text === 'object' && text !== null) {
          return JSON.stringify(text); // Basic object handling
        }
        return String(text); // Basic string conversion
      },
      ellipsis: true,
      width: 150, // Fixed width for horizontal scrolling
    }));
  }, [dbTableContent]);

  return (
    <div className="database-panel" style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Flex gap={8} align="center" style={{ flexShrink: 0 }}>
        <Select
          style={{ flex: 1, width: 0 }}
          placeholder={t('replay.right.selectTable')}
          onChange={handleTableChange}
          value={selectedTable}
          showSearch
          optionFilterProp="children"
        >
          {dbTables.map((t) => (
            <Option key={t} value={t}>{t}</Option>
          ))}
        </Select>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} />
      </Flex>

      {selectedTable && (
        <Button block icon={<TableOutlined />} onClick={showModal}>
          {t('replay.right.viewTable', { name: selectedTable })}
        </Button>
      )}

      {!selectedTable && (
        <div className="left-info-empty" style={{ marginTop: '12px', color: '#909399' }}>
          {t('replay.right.selectTableHint')}
        </div>
      )}

      <Modal
        title={t('replay.right.tableTitle', { name: selectedTable ?? '' })}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={null}
        width={1000}
        style={{ top: 20 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {selectedTable && dbTableContent?.tableName === selectedTable ? (
            <>
              <Table
                dataSource={dbTableContent.rows}
                columns={columns}
                size="small"
                pagination={false}
                scroll={{ x: 'max-content', y: 600 }}
                rowKey={(record: any, index?: number) => index!.toString()}
                loading={loading}
                bordered
              />
              <Flex justify="end">
                <Pagination
                  simple
                  current={currentPage}
                  total={dbTableContent.total}
                  pageSize={pageSize}
                  onChange={handlePageChange}
                  size="small"
                />
              </Flex>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 40 }}>
              {loading ? <Spin tip="加载中..." /> : '等待数据...'}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export const AgentRightPanel: React.FC = () => {
  const { t } = useTranslation();
  const { state, sendMessage } = useReplay();
  const {
    selectedAgentId,
    selectedAgentDialogs,
    agentProfiles,
    experimentInfo,
    socialProfile,
    socialPosts,
    socialDirectMessages,
    socialGroupMessages,
    allPosts,
    postCommentsMap,
  } = state;

  const profile = agentProfiles.get(selectedAgentId ?? -1);
  const hasSocial = experimentInfo?.has_social === true;

  const items = [
    {
      key: 'database',
      label: t('replay.right.database'),
      icon: <DatabaseOutlined />,
      children: <DatabaseTab />,
    },
    ...(hasSocial ? [{
      key: 'posts',
      label: t('replay.right.posts'),
      icon: <FileTextOutlined />,
      children: <PostsTab posts={allPosts} agentProfiles={agentProfiles} postCommentsMap={postCommentsMap} sendMessage={sendMessage} />,
    }] : []),
    ...(profile ? [
      {
        key: 'reflection',
        label: t('replay.right.reflection'),
        icon: <SmileOutlined />,
        children: <DialogsTab dialogs={selectedAgentDialogs} type={DialogType.THOUGHT} agentProfile={profile} agentProfiles={agentProfiles} emptyHint={t('replay.right.noReflection')} />,
      },
      ...(hasSocial ? [{
        key: 'chat',
        label: t('replay.right.chat'),
        icon: <MessageOutlined />,
        children: (
          <SocialTab
            agentId={selectedAgentId}
            agentProfiles={agentProfiles}
            profile={socialProfile}
            posts={socialPosts}
            directMessages={socialDirectMessages}
            groupMessages={socialGroupMessages}
          />
        ),
      }] : []),
    ] : []),
  ];

  const defaultKey = profile ? 'reflection' : (hasSocial ? 'posts' : 'database');

  return (
    <Flex vertical className="right-inner">
      <Tabs
        centered
        defaultActiveKey={defaultKey}
        animated={{ inkBar: true, tabPane: true }}
        className="tabs w-full"
        items={items}
      />
    </Flex>
  );
};

// 自定义 Bubble 组件替代 @ant-design/x Bubble.List
const BubbleItem: React.FC<{
  role: 'self';
  name: string;
  content: string;
  header: React.ReactNode;
}> = ({ role, name, content, header }) => {
  // Only self role remains for thoughts
  const avatarBg = '#fde3cf';

  return (
    <div className={`bubble-item bubble-left`}>
      <Avatar icon={<UserOutlined />} style={{ background: avatarBg, flexShrink: 0 }} />
      <div className="bubble-content">
        <div className="bubble-header">{header}</div>
        <div className="bubble-text">{content}</div>
      </div>
    </div>
  );
};

const DialogsTab: React.FC<{
  dialogs: AgentDialog[];
  type: DialogType;
  agentProfile: { id: number; name: string };
  agentProfiles: Map<number, { id: number; name: string }>;
  emptyHint: string;
}> = ({ dialogs, type, agentProfile, emptyHint }) => {
  // Filter by type (which should effectively always be THOUGHT now)
  const items = dialogs.filter((d) => d.type === type);

  if (items.length === 0) {
    return <div className="left-info-empty" style={{ marginTop: '12px', color: '#909399' }}>{emptyHint}</div>;
  }

  return (
    <div className="bubble-list">
      {items.map((m, i) => {
        // Try to parse content as JSON
        let content = m.content;
        try {
          const contentJson = JSON.parse(m.content);
          if (contentJson.content !== undefined) {
            content = contentJson.content;
          }
        } catch (e) {
          // Keep original content
        }

        return (
          <BubbleItem
            key={`${m.id}-${i}`}
            role="self"
            name={agentProfile?.name || 'Agent'}
            content={content}
            header={
              <span>
                {agentProfile?.name || 'Agent'} (Step {m.step} · {dayjs(m.t).format('HH:mm:ss')})
              </span>
            }
          />
        );
      })}
    </div>
  );
};

const labelStyle = { fontWeight: 400, color: '#909399' };
const valueStyle = { fontWeight: 600, color: '#007AFF' };

/** 帖子面板：按时间线展示所有用户帖子，点开查看内容与评论 */
const PostsTab: React.FC<{
  posts: SocialPost[];
  agentProfiles: Map<number, { id: number; name: string }>;
  postCommentsMap: Record<number, SocialComment[]>;
  sendMessage: (msg: any) => void;
}> = ({ posts, agentProfiles, postCommentsMap, sendMessage }) => {
  const { t } = useTranslation();
  const [detailOpen, setDetailOpen] = React.useState(false);
  const [detailPost, setDetailPost] = React.useState<SocialPost | null>(null);

  const sortedPosts = React.useMemo(() => {
    return [...posts].sort((a, b) => {
      const at = dayjs(a.created_at || 0).valueOf();
      const bt = dayjs(b.created_at || 0).valueOf();
      return bt - at;
    });
  }, [posts]);

  const openDetail = (post: SocialPost) => {
    setDetailPost(post);
    setDetailOpen(true);
    sendMessage({ command: 'fetchPostComments', postId: post.post_id });
  };

  const comments = detailPost ? (postCommentsMap[detailPost.post_id] ?? []) : [];
  const authorName = detailPost ? (agentProfiles.get(detailPost.author_id ?? 0)?.name ?? t('replay.right.userId', { id: detailPost.author_id })) : '';

  return (
    <Flex vertical style={{ width: '100%', height: '100%', minHeight: 0 }}>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {sortedPosts.length === 0 ? (
          <div className="left-info-empty" style={{ padding: 16, color: '#909399', textAlign: 'center' }}>{t('replay.right.noPosts')}</div>
        ) : (
          <List
            size="small"
            dataSource={sortedPosts}
            renderItem={(post) => {
              const name = agentProfiles.get(post.author_id ?? 0)?.name ?? t('replay.right.userId', { id: post.author_id });
              const preview = (post.content || '').slice(0, 40);
              return (
                <List.Item
                  style={{ cursor: 'pointer', borderRadius: 8, padding: '8px 12px' }}
                  onClick={() => openDetail(post)}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
                >
                  <List.Item.Meta
                    avatar={<Avatar size="small" icon={<UserOutlined />} style={{ background: '#e5e5e5' }} />}
                    title={<span>{name} · Step {(post as any).step ?? '—'}</span>}
                    description={
                      post.created_at
                        ? `${dayjs(post.created_at).format('MM-DD HH:mm')} · ${preview}${(post.content?.length ?? 0) > 40 ? '…' : ''}`
                        : preview || '—'
                    }
                  />
                </List.Item>
              );
            }}
          />
        )}
      </div>

      <Modal
        title={detailPost ? t('replay.right.postByAuthor', { author: authorName }) : t('replay.right.postDetail')}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={480}
        bodyStyle={{ maxHeight: 560, overflowY: 'auto', padding: 16 }}
        closeIcon={<CloseOutlined />}
      >
        {detailPost && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: 12, background: 'rgba(0,0,0,0.04)', borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#909399', marginBottom: 6 }}>
                {authorName} · {detailPost.created_at ? dayjs(detailPost.created_at).format('YYYY-MM-DD HH:mm') : '—'}
              </div>
              <div style={{ lineHeight: 1.6, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>{detailPost.content}</div>
              <div style={{ fontSize: 11, color: '#909399', marginTop: 8 }}>
                {t('replay.right.likes')} {detailPost.likes_count ?? 0} · {t('replay.right.comments')} {detailPost.comments_count ?? 0} · {t('replay.right.reposts')} {detailPost.reposts_count ?? 0}
              </div>
            </div>
            <Divider style={{ margin: '8px 0' }}>{t('replay.right.commentsSection')}</Divider>
            {comments.length === 0 ? (
              <div style={{ color: '#909399', fontSize: 12, textAlign: 'center' }}>{t('replay.right.noComments')}</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {comments.map((c) => (
                  <div key={c.comment_id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <Avatar size={28} icon={<UserOutlined />} style={{ flexShrink: 0, background: '#e5e5e5' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: '#576b95', marginBottom: 2 }}>
                        {agentProfiles.get(c.author_id)?.name ?? t('replay.right.userId', { id: c.author_id })}
                      </div>
                      <div style={{ fontSize: 13, lineHeight: 1.5, wordBreak: 'break-word' }}>{c.content}</div>
                      <div style={{ fontSize: 11, color: '#909399', marginTop: 4 }}>
                        {c.created_at ? dayjs(c.created_at).format('MM-DD HH:mm') : '—'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>
    </Flex>
  );
};

type DmConversation = { peerId: number; peerName: string; messages: SocialDirectMessage[] };
type GroupConversation = { groupId: number; groupName: string; messages: SocialGroupMessage[] };

const SocialTab: React.FC<{
  agentId: number | null;
  agentProfiles: Map<number, { id: number; name: string }>;
  profile: SocialUser | null;
  posts: SocialPost[];
  directMessages: SocialDirectMessage[];
  groupMessages: SocialGroupMessage[];
}> = ({ agentId, agentProfiles, profile, posts, directMessages, groupMessages }) => {
  const { t } = useTranslation();
  const [chatModalOpen, setChatModalOpen] = React.useState(false);
  const [chatModalTitle, setChatModalTitle] = React.useState('');
  const [chatModalDm, setChatModalDm] = React.useState<SocialDirectMessage[] | null>(null);
  const [chatModalGroup, setChatModalGroup] = React.useState<SocialGroupMessage[] | null>(null);

  const dmConversations = React.useMemo((): DmConversation[] => {
    if (agentId == null || directMessages.length === 0) return [];
    const byPeer = new Map<number, SocialDirectMessage[]>();
    for (const m of directMessages) {
      const peer = m.from_user_id === agentId ? m.to_user_id : m.from_user_id;
      if (!byPeer.has(peer)) byPeer.set(peer, []);
      byPeer.get(peer)!.push(m);
    }
    return Array.from(byPeer.entries()).map(([peerId, messages]) => {
      const sorted = [...messages].sort((a, b) =>
        dayjs(a.created_at || 0).valueOf() - dayjs(b.created_at || 0).valueOf()
      );
      const peerName = agentProfiles.get(peerId)?.name ?? t('replay.right.userId', { id: peerId });
      return { peerId, peerName, messages: sorted };
    }).sort((a, b) => {
      const at = a.messages[a.messages.length - 1]?.created_at;
      const bt = b.messages[b.messages.length - 1]?.created_at;
      return dayjs(bt || 0).valueOf() - dayjs(at || 0).valueOf();
    });
  }, [agentId, directMessages, agentProfiles]);

  const groupConversations = React.useMemo((): GroupConversation[] => {
    if (groupMessages.length === 0) return [];
    const byGroup = new Map<number, SocialGroupMessage[]>();
    for (const m of groupMessages) {
      if (!byGroup.has(m.group_id)) byGroup.set(m.group_id, []);
      byGroup.get(m.group_id)!.push(m);
    }
    return Array.from(byGroup.entries()).map(([groupId, messages]) => {
      const sorted = [...messages].sort((a, b) =>
        dayjs(a.created_at || 0).valueOf() - dayjs(b.created_at || 0).valueOf()
      );
      const groupName = messages[0]?.group_name ?? `群组 ${groupId}`;
      return { groupId, groupName, messages: sorted };
    }).sort((a, b) => {
      const at = a.messages[a.messages.length - 1]?.created_at;
      const bt = b.messages[b.messages.length - 1]?.created_at;
      return dayjs(bt || 0).valueOf() - dayjs(at || 0).valueOf();
    });
  }, [groupMessages]);

  const openDmModal = (conv: DmConversation) => {
    setChatModalTitle(t('replay.right.conversationWith', { name: conv.peerName }));
    setChatModalDm(conv.messages);
    setChatModalGroup(null);
    setChatModalOpen(true);
  };
  const openGroupModal = (conv: GroupConversation) => {
    setChatModalTitle(conv.groupName);
    setChatModalDm(null);
    setChatModalGroup(conv.messages);
    setChatModalOpen(true);
  };

  const chatMessages = chatModalDm ?? chatModalGroup ?? [];
  const isDm = chatModalDm != null;
  const currentAgentId = agentId ?? -1;

  return (
    <Flex vertical style={{ width: '100%', height: '100%', minHeight: 0 }}>
      {/* 社交档案 折叠在顶部一行 */}
      {profile && (
        <Flex wrap justify="flex-start" align="center" style={{ width: '100%', marginBottom: 8, gap: 8 }}>
          <span style={labelStyle}>{t('replay.right.username')}</span>
          <span style={valueStyle}>{profile.username}</span>
          <span style={labelStyle}>{t('replay.right.following')}</span>
          <span style={valueStyle}>{profile.following_count}</span>
          <span style={labelStyle}>{t('replay.right.followers')}</span>
          <span style={valueStyle}>{profile.followers_count}</span>
        </Flex>
      )}

      <Tabs
        size="small"
        style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}
        items={[
          {
            key: 'dm',
            label: (
              <span>
                <MessageOutlined /> 私聊 {dmConversations.length > 0 && `(${dmConversations.length})`}
              </span>
            ),
            children: (
              <div style={{ height: '100%', overflow: 'auto' }}>
                {dmConversations.length === 0 ? (
                  <div className="left-info-empty" style={{ padding: 16, color: '#909399', textAlign: 'center' }}>暂无私信</div>
                ) : (
                  <List
                    size="small"
                    dataSource={dmConversations}
                    renderItem={(conv) => {
                      const last = conv.messages[conv.messages.length - 1];
                      const preview = last?.content?.slice(0, 20) ?? '';
                      return (
                        <List.Item
                          style={{ cursor: 'pointer', borderRadius: 8, padding: '8px 12px' }}
                          onClick={() => openDmModal(conv)}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
                        >
                          <List.Item.Meta
                            avatar={<Avatar size="small" icon={<UserOutlined />} style={{ background: '#e5e5e5' }} />}
                            title={t('replay.right.conversationWith', { name: conv.peerName })}
                            description={
                              last?.created_at
                                ? `${dayjs(last.created_at).format('MM-DD HH:mm')} · ${preview}${(last.content?.length ?? 0) > 20 ? '…' : ''}`
                                : t('replay.right.messagesCount', { count: conv.messages.length })
                            }
                          />
                        </List.Item>
                      );
                    }}
                  />
                )}
              </div>
            ),
          },
          {
            key: 'group',
            label: (
              <span>
                <TeamOutlined /> 群聊 {groupConversations.length > 0 && `(${groupConversations.length})`}
              </span>
            ),
            children: (
              <div style={{ height: '100%', overflow: 'auto' }}>
                {groupConversations.length === 0 ? (
                  <div className="left-info-empty" style={{ padding: 16, color: '#909399', textAlign: 'center' }}>暂无群聊</div>
                ) : (
                  <List
                    size="small"
                    dataSource={groupConversations}
                    renderItem={(conv) => {
                      const last = conv.messages[conv.messages.length - 1];
                      const preview = last?.content?.slice(0, 20) ?? '';
                      return (
                        <List.Item
                          style={{ cursor: 'pointer', borderRadius: 8, padding: '8px 12px' }}
                          onClick={() => openGroupModal(conv)}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.04)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
                        >
                          <List.Item.Meta
                            avatar={<Avatar size="small" icon={<TeamOutlined />} style={{ background: '#e5e5e5' }} />}
                            title={conv.groupName}
                            description={
                              last?.created_at
                                ? `${dayjs(last.created_at).format('MM-DD HH:mm')} · ${preview}${(last.content?.length ?? 0) > 20 ? '…' : ''}`
                                : t('replay.right.messagesCount', { count: conv.messages.length })
                            }
                          />
                        </List.Item>
                      );
                    }}
                  />
                )}
              </div>
            ),
          },
        ]}
      />

      {/* 消息悬浮窗：点击会话后展示具体聊天内容（QQ/微信风格） */}
      <Modal
        title={chatModalTitle}
        open={chatModalOpen}
        onCancel={() => setChatModalOpen(false)}
        footer={null}
        width={440}
        bodyStyle={{ maxHeight: 520, overflowY: 'auto', padding: 16 }}
        closeIcon={<CloseOutlined />}
        styles={{ body: { paddingTop: 12 } }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {chatMessages.map((msg: SocialDirectMessage | SocialGroupMessage) => {
            const isSelf = msg.from_user_id === currentAgentId;
            const senderName = agentProfiles.get(msg.from_user_id)?.name ?? t('replay.right.userId', { id: msg.from_user_id });
            const msgKey = 'message_id' in msg ? msg.message_id : (msg as SocialGroupMessage).message_id;
            const bubble = (
              <div
                style={{
                  maxWidth: '78%',
                  padding: '10px 14px',
                  borderRadius: 8,
                  borderTopRightRadius: isSelf ? 2 : 8,
                  borderTopLeftRadius: isSelf ? 8 : 2,
                  background: isSelf ? '#95EC69' : '#fff',
                  color: isSelf ? '#000' : '#333',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
                }}
              >
                {!isDm && (
                  <div style={{ fontSize: 12, color: '#576b95', marginBottom: 4, fontWeight: 500 }}>{senderName}</div>
                )}
                <div style={{ lineHeight: 1.5, wordBreak: 'break-word', fontSize: 14 }}>{msg.content}</div>
                <div style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginTop: 6, textAlign: 'right' }}>
                  {msg.created_at ? dayjs(msg.created_at).format('HH:mm') : '—'}
                </div>
              </div>
            );
            return (
              <div
                key={msgKey}
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: isSelf ? 'flex-end' : 'flex-start',
                  gap: 8,
                }}
              >
                {!isSelf && (
                  <Avatar size={36} icon={<UserOutlined />} style={{ flexShrink: 0, background: '#e5e5e5' }} />
                )}
                {bubble}
                {isSelf && (
                  <Avatar size={36} icon={<UserOutlined />} style={{ flexShrink: 0, background: '#95EC69', color: '#333' }} />
                )}
              </div>
            );
          })}
        </div>
      </Modal>
    </Flex>
  );
};
