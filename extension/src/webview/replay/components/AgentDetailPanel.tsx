/**
 * 左侧信息面板
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Typography, Flex, Tooltip, Divider, Button, List } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import { AgentProfile, AgentStatus, SocialUser } from '../types';
import { PANEL_ICONS } from '../icons';

const { Title } = Typography;

const PROFILE_KEYS = ['name', 'gender', 'age', 'education', 'occupation', 'marriage_status', 'background_story'] as const;

export const AgentDetailPanel: React.FC = () => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const { selectedAgentId, agentProfiles, agentStatuses, agentStatusHistory, timeline, currentStep, socialProfile } = state;
  const currentStepNumber = timeline[currentStep]?.step ?? null;
  const historyList = Array.isArray(agentStatusHistory) ? agentStatusHistory : [];

  const profile = agentProfiles.get(selectedAgentId ?? -1);
  const status = agentStatuses.get(selectedAgentId ?? -1);

  const getTranslatedKey = (key: string): string => {
    const v = t(`replay.left.${key}` as any);
    return typeof v === 'string' && !v.startsWith('replay.') ? v : key;
  };

  const agentName = profile ? (profile.name !== '' ? profile.name : t('replay.left.unknown')) : t('replay.left.selectAgentPlaceholder');
  const rootClass = profile ? 'left-inner' : 'left-inner collapsed';

  const handleClose = () => {
    actions.selectAgent(null);
  };

  return (
    <Flex vertical justify="flex-start" align="center" className={rootClass}>
      {/* Header: Agent Information */}
      <Flex gap="small" align="center" style={{ marginTop: '8px', width: '100%' }}>
        <img src={PANEL_ICONS.info} width="32" height="32" alt="info" />
        <Title level={4} style={{ margin: 0, flex: 1 }}>{t('replay.left.agentInfo')}</Title>
        <Button
          shape="circle"
          icon={<CloseOutlined />}
          size="small"
          type="text"
          onClick={handleClose}
        />
      </Flex>

      {/* Profile Fields */}
      {profile ? (
        <>
          <Flex wrap justify="left" style={{ width: '100%', marginTop: '8px' }}>
            {/* Name */}
            <Flex className="left-info-block" justify="space-between">
              <span style={{ fontWeight: 400, color: '#909399' }}>{t('replay.left.name')}:&nbsp;&nbsp;</span>
              <Tooltip title={<span>ID = {profile.id}</span>}>
                <span style={{ fontWeight: 600, color: '#007AFF' }}>{agentName}</span>
              </Tooltip>
            </Flex>
            {/* Dynamic profile fields */}
            {profile.profile && Object.entries(profile.profile).map(([k, v]) => {
              if (k === 'name' || k === 'agent_id') return null; // Skip name and agent_id
              const isLongField = k === 'background_story';
              return (
                <Flex
                  className={isLongField ? 'left-info-block-status' : 'left-info-block'}
                  justify="space-between"
                  key={k}
                >
                  <span style={{ fontWeight: 400, color: '#909399' }}>{getTranslatedKey(k)}:&nbsp;&nbsp;</span>
                  <Tooltip title={<span>{v}</span>}>
                    <span style={{
                      fontWeight: 600,
                      color: '#007AFF',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: '70%',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical' as any,
                      lineHeight: '1.2em'
                    }}>
                      {v}
                    </span>
                  </Tooltip>
                </Flex>
              );
            })}
          </Flex>

          <Divider style={{ margin: '12px 0' }} />

          {/* Current Status */}
          <Flex gap="small" align="center" style={{ width: '100%' }}>
            <img src={PANEL_ICONS.status} width="32" height="32" alt="status" />
            <Title level={4} style={{ margin: 0 }}>{t('replay.left.currentStatus')}</Title>
          </Flex>

          <Flex wrap justify="left" className="w-full" style={{ marginTop: '8px' }}>
            <Flex vertical className="w-full">
              {status?.t && (
                <strong style={{ marginBottom: '4px' }}>
                  {new Date(status.t).toLocaleString()}
                </strong>
              )}
              {status?.action && (
                <span style={{ marginBottom: '8px' }}>{status.action}</span>
              )}

              {/* Status details */}
              {status?.status && typeof status.status === 'object' && (
                <Flex wrap justify="left">
                  {Object.entries(status.status).map(([k, v]) => {
                    // Skip complex nested objects; skip thought (shown in blue block below)
                    if (k === 'thought' || (typeof v === 'object' && v !== null)) return null;
                    return (
                      <Tooltip title="Click to show as heatmap" key={k}>
                        <Flex className="left-info-block" justify="space-between">
                          <span style={{ fontWeight: 400, color: '#909399' }}>{getTranslatedKey(k)}:&nbsp;&nbsp;</span>
                          <span style={{ fontWeight: 600, color: '#007AFF' }}>
                            {typeof v === 'number' ? (v as number).toFixed(2) : String(v)}
                          </span>
                        </Flex>
                      </Tooltip>
                    );
                  })}
                </Flex>
              )}

              {/* Thought/reflection in blue italic */}
              {status?.status?.thought && (
                <div style={{
                  marginTop: '8px',
                  padding: '8px 12px',
                  background: 'rgba(0, 122, 255, 0.08)',
                  borderRadius: '8px',
                  color: '#007AFF',
                  fontStyle: 'italic',
                  lineHeight: '1.5'
                }}>
                  {status.status.thought}
                </div>
              )}
            </Flex>
          </Flex>

          <Divider style={{ margin: '12px 0' }} />

          {/* Status History */}
          <Flex gap="small" align="center" style={{ width: '100%' }}>
            <img src={PANEL_ICONS.history} width="32" height="32" alt="history" />
            <Title level={4} style={{ margin: 0 }}>Status History</Title>
          </Flex>
          <Flex vertical className="w-full" style={{ marginTop: '8px', minHeight: '48px' }}>
            {historyList.length === 0 ? (
              <div className="left-info-history-card" style={{ minHeight: '40px', display: 'flex', alignItems: 'center' }}>
                <div className="left-info-history-inner" style={{ color: '#909399', width: '100%' }}>
                  No history data
                </div>
              </div>
            ) : (
              <List
                size="small"
                dataSource={[...historyList].sort((a, b) => a.step - b.step)}
                renderItem={(entry) => {
                  const isCurrentStep = currentStepNumber !== null && entry.step === currentStepNumber;
                  return (
                    <List.Item
                      key={entry.step}
                      style={{
                        padding: '8px 12px',
                        marginBottom: '6px',
                        borderRadius: '8px',
                        background: isCurrentStep ? 'rgba(0, 122, 255, 0.12)' : 'rgba(0,0,0,0.04)',
                        border: isCurrentStep ? '1px solid rgba(0, 122, 255, 0.4)' : '1px solid transparent',
                      }}
                    >
                      <Flex vertical gap={4} style={{ width: '100%' }}>
                        <Flex justify="space-between" align="center">
                          <span style={{ fontWeight: 600, color: '#007AFF', fontSize: '12px' }}>
                            Step {entry.step}
                            {isCurrentStep && ' (current)'}
                          </span>
                          <span style={{ fontSize: '11px', color: '#909399' }}>
                            {entry.t ? new Date(entry.t).toLocaleString() : ''}
                          </span>
                        </Flex>
                        {entry.action && (
                          <span style={{ fontSize: '12px', color: '#303133' }}>{entry.action}</span>
                        )}
                        {entry.status?.emotion_type && (
                          <span style={{ fontSize: '11px', color: '#606266' }}>
                            emotion_type: {String(entry.status.emotion_type)}
                          </span>
                        )}
                        {entry.status?.thought && (
                          <span
                            style={{
                              fontSize: '11px',
                              color: '#606266',
                              fontStyle: 'italic',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical' as any,
                              overflow: 'hidden',
                            }}
                          >
                            {String(entry.status.thought)}
                          </span>
                        )}
                      </Flex>
                    </List.Item>
                  );
                }}
              />
            )}
          </Flex>
        </>
      ) : (
        <div className="left-info-empty" style={{ marginTop: '20px', color: '#909399' }}>
          {t('replay.left.selectAgent')}
        </div>
      )}
    </Flex>
  );
};
