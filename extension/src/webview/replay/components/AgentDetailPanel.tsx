/**
 * Left-side agent information and per-agent state panel
 */

import * as React from 'react';
import { Button, Divider, Flex, List, Select, Tooltip, Typography } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import type { ReplayDatasetColumn, ReplayDatasetInfo } from '../types';
import { PANEL_ICONS } from '../icons';

const { Title } = Typography;

function formatValue(value: any): React.ReactNode {
  if (value === null || value === undefined) {
    return <span style={{ color: '#909399' }}>-</span>;
  }
  if (typeof value === 'object') {
    return (
      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '11px' }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return String(value);
}

function getColumnLabel(columns: ReplayDatasetColumn[], key: string): string {
  return columns.find((column) => column.column_name === key)?.title || key;
}

const DatasetRowCard: React.FC<{
  dataset: ReplayDatasetInfo;
  row: Record<string, any> | null | undefined;
}> = ({ dataset, row }) => {
  if (!row) {
    return (
      <div className="left-info-history-card" style={{ marginTop: '8px' }}>
        <div className="left-info-history-inner" style={{ color: '#909399' }}>
          No current row at this step
        </div>
      </div>
    );
  }

  const entries = Object.entries(row).filter(([key]) => !['agent_id'].includes(key));

  return (
    <div className="left-info-history-card" style={{ marginTop: '8px' }}>
      <div className="left-info-history-inner">
        <div style={{ fontWeight: 600, color: '#1677ff', marginBottom: '8px' }}>
          {dataset.title || dataset.dataset_id}
        </div>
        <div style={{ fontSize: '11px', color: '#909399', marginBottom: '8px' }}>
          {dataset.module_name} / {dataset.dataset_id}
        </div>
        <Flex vertical gap={8}>
          {entries.map(([key, value]) => (
            <div key={key}>
              <div style={{ fontSize: '11px', color: '#909399', marginBottom: '2px' }}>
                {getColumnLabel(dataset.columns, key)}
              </div>
              <div style={{ color: '#303133' }}>{formatValue(value)}</div>
            </div>
          ))}
        </Flex>
      </div>
    </div>
  );
};

export const AgentDetailPanel: React.FC = () => {
  const { state, actions } = useReplay();
  const {
    selectedAgentId,
    agentProfiles,
    panelSchema,
    agentStateRowsAtStep,
    selectedAgentHistoryByDataset,
    selectedAgentHistoryDatasetId,
    timeline,
    currentStep,
  } = state;

  const profile = agentProfiles.get(selectedAgentId ?? -1);
  const currentStepNumber = timeline[currentStep]?.step ?? null;
  const agentStateDatasets = panelSchema?.agent_state_datasets ?? [];
  const datasetMap = React.useMemo(
    () => new Map(agentStateDatasets.map((dataset) => [dataset.dataset_id, dataset])),
    [agentStateDatasets]
  );
  const historyDatasetId = selectedAgentHistoryDatasetId || panelSchema?.primary_agent_state_dataset_id || null;
  const historyDataset = historyDatasetId ? datasetMap.get(historyDatasetId) ?? null : null;
  const historyRows = historyDatasetId ? (selectedAgentHistoryByDataset[historyDatasetId] ?? []) : [];
  const currentRows = selectedAgentId === null
    ? []
    : agentStateDatasets.map((dataset) => ({
      dataset,
      row: agentStateRowsAtStep[dataset.dataset_id]?.rows_by_agent_id[String(selectedAgentId)] ?? null,
    }));

  const rootClass = profile ? 'left-inner' : 'left-inner collapsed';

  return (
    <Flex vertical justify="flex-start" align="center" className={rootClass}>
      <Flex gap="small" align="center" style={{ marginTop: '8px', width: '100%' }}>
        <img src={PANEL_ICONS.info} width="32" height="32" alt="info" />
        <Title level={4} style={{ margin: 0, flex: 1 }}>Agent Info</Title>
        <Button
          shape="circle"
          icon={<CloseOutlined />}
          size="small"
          type="text"
          onClick={() => actions.selectAgent(null)}
        />
      </Flex>

      {profile ? (
        <>
          <Flex wrap justify="left" style={{ width: '100%', marginTop: '8px' }}>
            <Flex className="left-info-block" justify="space-between">
              <span style={{ fontWeight: 400, color: '#909399' }}>Name:&nbsp;&nbsp;</span>
              <Tooltip title={<span>ID = {profile.id}</span>}>
                <span style={{ fontWeight: 600, color: '#007AFF' }}>{profile.name}</span>
              </Tooltip>
            </Flex>
            {Object.entries(profile.profile ?? {}).map(([key, value]) => (
              <Flex
                className={typeof value === 'object' ? 'left-info-block-status' : 'left-info-block'}
                justify="space-between"
                key={key}
              >
                <span style={{ fontWeight: 400, color: '#909399' }}>{key}:&nbsp;&nbsp;</span>
                <div style={{ fontWeight: 600, color: '#007AFF', maxWidth: '72%', overflow: 'hidden' }}>
                  {formatValue(value)}
                </div>
              </Flex>
            ))}
          </Flex>

          <Divider style={{ margin: '12px 0' }} />

          <Flex gap="small" align="center" style={{ width: '100%' }}>
            <img src={PANEL_ICONS.status} width="32" height="32" alt="status" />
            <Title level={4} style={{ margin: 0 }}>Current Per-Agent State</Title>
          </Flex>

          <div style={{ width: '100%', marginTop: '8px' }}>
            {currentRows.length === 0 ? (
              <div className="left-info-empty">No per-agent state datasets</div>
            ) : (
              currentRows.map(({ dataset, row }) => (
                <DatasetRowCard key={dataset.dataset_id} dataset={dataset} row={row} />
              ))
            )}
          </div>

          <Divider style={{ margin: '12px 0' }} />

          <Flex gap="small" align="center" style={{ width: '100%' }}>
            <img src={PANEL_ICONS.history} width="32" height="32" alt="history" />
            <Title level={4} style={{ margin: 0, flex: 1 }}>State History</Title>
          </Flex>

          {agentStateDatasets.length > 0 && (
            <Select
              style={{ width: '100%', marginTop: '8px' }}
              value={historyDatasetId ?? undefined}
              options={agentStateDatasets.map((dataset) => ({
                value: dataset.dataset_id,
                label: dataset.title || dataset.dataset_id,
              }))}
              onChange={(value) => actions.setSelectedAgentHistoryDatasetId(value)}
            />
          )}

          <Flex vertical className="w-full" style={{ marginTop: '8px', minHeight: '48px', width: '100%' }}>
            {!historyDataset ? (
              <div className="left-info-empty">No state history dataset selected</div>
            ) : historyRows.length === 0 ? (
              <div className="left-info-history-card" style={{ minHeight: '40px', display: 'flex', alignItems: 'center' }}>
                <div className="left-info-history-inner" style={{ color: '#909399', width: '100%' }}>
                  No history data
                </div>
              </div>
            ) : (
              <List
                size="small"
                dataSource={[...historyRows].sort((a, b) => Number(b.step ?? -1) - Number(a.step ?? -1))}
                renderItem={(row) => {
                  const isCurrentStep = currentStepNumber !== null && Number(row.step) === currentStepNumber;
                  const entries = Object.entries(row).filter(([key]) => !['agent_id', 'step', 't'].includes(key));
                  return (
                    <List.Item
                      key={`${historyDataset.dataset_id}-${row.step}-${row.t ?? 'na'}`}
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
                            Step {String(row.step)}
                            {isCurrentStep && ' (current)'}
                          </span>
                          <span style={{ fontSize: '11px', color: '#909399' }}>
                            {row.t ? new Date(String(row.t)).toLocaleString() : ''}
                          </span>
                        </Flex>
                        {entries.map(([key, value]) => (
                          <div key={key}>
                            <div style={{ fontSize: '11px', color: '#909399', marginBottom: '2px' }}>
                              {getColumnLabel(historyDataset.columns, key)}
                            </div>
                            <div style={{ fontSize: '12px', color: '#303133' }}>
                              {formatValue(value)}
                            </div>
                          </div>
                        ))}
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
          Select an agent from the scene
        </div>
      )}
    </Flex>
  );
};
