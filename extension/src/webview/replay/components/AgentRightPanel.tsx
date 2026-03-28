/**
 * 右侧对话/社交/指标面板
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs, Flex, Avatar, Select, Table, Pagination, Button, Spin, Modal, Divider, List } from 'antd';
import { SmileOutlined, UserOutlined, DatabaseOutlined, ReloadOutlined, TableOutlined, MessageOutlined, CloseOutlined, FileTextOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import {
  DialogType,
  AgentDialog,
  SocialPost,
  SocialComment,
  SocialEvent,
  SocialUser,
  ReplayDatasetInfo,
} from '../types';
import dayjs from 'dayjs';

const { Option } = Select;

const DatabaseTab: React.FC = () => {
  const { t } = useTranslation();
  const { state, sendMessage } = useReplay();
  const { replayDatasets, replayDatasetRows, loading } = state;
  const [selectedDatasetId, setSelectedDatasetId] = React.useState<string | null>(null);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [isModalVisible, setIsModalVisible] = React.useState(false);
  const pageSize = 20;
  const selectedDataset = React.useMemo(
    () => replayDatasets.find((dataset) => dataset.dataset_id === selectedDatasetId) ?? null,
    [replayDatasets, selectedDatasetId]
  );

  React.useEffect(() => {
    sendMessage({ command: 'fetchReplayDatasets' });
  }, [sendMessage]);

  const handleDatasetChange = (value: string) => {
    setSelectedDatasetId(value);
    setCurrentPage(1);
    sendMessage({ command: 'fetchReplayDatasetRows', datasetId: value, page: 1, pageSize });
    setIsModalVisible(true);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    if (selectedDatasetId) {
      sendMessage({ command: 'fetchReplayDatasetRows', datasetId: selectedDatasetId, page, pageSize });
    }
  };

  const handleRefresh = () => {
    sendMessage({ command: 'fetchReplayDatasets' });
    if (selectedDatasetId) {
      sendMessage({ command: 'fetchReplayDatasetRows', datasetId: selectedDatasetId, page: currentPage, pageSize });
    }
  };

  const showModal = () => {
    if (selectedDatasetId) {
      setIsModalVisible(true);
    }
  };

  const handleCancel = () => {
    setIsModalVisible(false);
  };

  const columns = React.useMemo(() => {
    if (!replayDatasetRows || !replayDatasetRows.columns) return [];
    return replayDatasetRows.columns.map((col) => ({
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
  }, [replayDatasetRows]);

  const renderDatasetLabel = (dataset: ReplayDatasetInfo) =>
    dataset.title?.trim()
      ? `${dataset.title} (${dataset.dataset_id})`
      : dataset.dataset_id;

  return (
    <div className="database-panel" style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Flex gap={8} align="center" style={{ flexShrink: 0 }}>
        <Select
          style={{ flex: 1, width: 0 }}
          placeholder={t('replay.right.selectTable')}
          onChange={handleDatasetChange}
          value={selectedDatasetId}
          showSearch
          optionFilterProp="children"
        >
          {replayDatasets.map((dataset) => (
            <Option key={dataset.dataset_id} value={dataset.dataset_id}>
              {renderDatasetLabel(dataset)}
            </Option>
          ))}
        </Select>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} />
      </Flex>

      {selectedDatasetId && (
        <Button block icon={<TableOutlined />} onClick={showModal}>
          {t('replay.right.viewTable', { name: selectedDatasetId })}
        </Button>
      )}

      {!selectedDatasetId && (
        <div className="left-info-empty" style={{ marginTop: '12px', color: '#909399' }}>
          {t('replay.right.selectTableHint')}
        </div>
      )}

      {selectedDataset && (
        <div style={{ fontSize: 12, color: '#909399', lineHeight: 1.5 }}>
          <div>{selectedDataset.module_name} / {selectedDataset.kind}</div>
          {selectedDataset.description ? <div>{selectedDataset.description}</div> : null}
        </div>
      )}

      <Modal
        title={t('replay.right.tableTitle', { name: selectedDatasetId ?? '' })}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={null}
        width={1000}
        style={{ top: 20 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {selectedDatasetId && replayDatasetRows?.dataset_id === selectedDatasetId ? (
            <>
              <Table
                dataSource={replayDatasetRows.rows}
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
                  total={replayDatasetRows.total}
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
    socialEvents,
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
        key: 'social',
        label: t('replay.right.chat'),
        icon: <MessageOutlined />,
        children: (
          <SocialTab
            agentId={selectedAgentId}
            agentProfiles={agentProfiles}
            profile={socialProfile}
            posts={socialPosts}
            events={socialEvents}
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
  const authorName = detailPost ? (agentProfiles.get(detailPost.author_id)?.name ?? t('replay.right.userId', { id: detailPost.author_id })) : '';

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
              const name = agentProfiles.get(post.author_id)?.name ?? t('replay.right.userId', { id: post.author_id });
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

const SocialTab: React.FC<{
  agentId: number | null;
  agentProfiles: Map<number, { id: number; name: string }>;
  profile: SocialUser | null;
  posts: SocialPost[];
  events: SocialEvent[];
}> = ({ agentId, agentProfiles, profile, posts, events }) => {
  const { t } = useTranslation();
  const sortedEvents = React.useMemo(
    () =>
      [...events].sort((a, b) => {
        const at = dayjs(a.t || 0).valueOf();
        const bt = dayjs(b.t || 0).valueOf();
        if (at !== bt) return bt - at;
        if (a.step !== b.step) return b.step - a.step;
        return b.event_id - a.event_id;
      }),
    [events]
  );
  const sortedPosts = React.useMemo(
    () =>
      [...posts].sort((a, b) => {
        const at = dayjs(a.created_at || 0).valueOf();
        const bt = dayjs(b.created_at || 0).valueOf();
        if (at !== bt) return bt - at;
        if ((a.step ?? 0) !== (b.step ?? 0)) return (b.step ?? 0) - (a.step ?? 0);
        return b.post_id - a.post_id;
      }),
    [posts]
  );

  return (
    <Flex vertical style={{ width: '100%', height: '100%', minHeight: 0 }}>
      {profile && (
        <Flex wrap justify="flex-start" align="center" style={{ width: '100%', marginBottom: 8, gap: 8 }}>
          <span style={labelStyle}>{t('replay.right.username')}</span>
          <span style={valueStyle}>{profile.username}</span>
          <span style={labelStyle}>Posts</span>
          <span style={valueStyle}>{profile.posts_count}</span>
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
            key: 'events',
            label: (
              <span>
                <MessageOutlined /> Activity {sortedEvents.length > 0 && `(${sortedEvents.length})`}
              </span>
            ),
            children: (
              <div style={{ height: '100%', overflow: 'auto' }}>
                {sortedEvents.length === 0 ? (
                  <div className="left-info-empty" style={{ padding: 16, color: '#909399', textAlign: 'center' }}>暂无社交事件</div>
                ) : (
                  <List
                    size="small"
                    dataSource={sortedEvents}
                    renderItem={(event) => {
                      const secondary = [
                        `Step ${event.step}`,
                        event.t ? dayjs(event.t).format('MM-DD HH:mm:ss') : null,
                        event.action,
                      ].filter(Boolean).join(' · ');
                      return (
                        <List.Item
                          style={{ borderRadius: 8, padding: '8px 12px', alignItems: 'flex-start' }}
                        >
                          <List.Item.Meta
                            avatar={<Avatar size="small" icon={<UserOutlined />} style={{ background: '#e5e5e5' }} />}
                            title={<span>{event.summary}</span>}
                            description={secondary}
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
            key: 'posts',
            label: (
              <span>
                <FileTextOutlined /> My Posts {sortedPosts.length > 0 && `(${sortedPosts.length})`}
              </span>
            ),
            children: (
              <div style={{ height: '100%', overflow: 'auto' }}>
                {sortedPosts.length === 0 ? (
                  <div className="left-info-empty" style={{ padding: 16, color: '#909399', textAlign: 'center' }}>暂无帖子</div>
                ) : (
                  <List
                    size="small"
                    dataSource={sortedPosts}
                    renderItem={(post) => {
                      const authorName =
                        agentProfiles.get(post.author_id)?.name
                        ?? t('replay.right.userId', { id: post.author_id });
                      const preview = (post.content || '').slice(0, 40);
                      return (
                        <List.Item
                          style={{ borderRadius: 8, padding: '8px 12px', alignItems: 'flex-start' }}
                        >
                          <List.Item.Meta
                            avatar={<Avatar size="small" icon={<UserOutlined />} style={{ background: '#e5e5e5' }} />}
                            title={<span>{authorName} · Step {post.step ?? '—'}</span>}
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
            ),
          },
        ]}
      />
    </Flex>
  );
};
