/**
 * Replay App - Main component for simulation replay
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ExtensionMessage, InitData } from './types';
import { ReplayProvider, useReplay } from './store';
import { TimelinePlayer, AgentDetailPanel, AgentMap, AgentRightPanel } from './components';

interface ReplayAppProps {
  vscode: VSCodeAPI;
}

/** Main app wrapper with provider */
export const ReplayApp: React.FC<ReplayAppProps> = ({ vscode }) => {
  return (
    <ReplayProvider vscode={vscode}>
      <ReplayAppInner vscode={vscode} />
    </ReplayProvider>
  );
};

/** Inner app component */
const ReplayAppInner: React.FC<ReplayAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const { initialized, loading, error, initData, currentStep, selectedAgentId, timeline } = state;

  // Handle messages from extension
  React.useEffect(() => {
    const handleMessage = (event: MessageEvent<ExtensionMessage>) => {
      const message = event.data;

      switch (message.type) {
        case 'init':
          actions.setInitData(message.data);
          actions.setLoading(true);
          // Fetch experiment info first; timeline/profiles/social are requested after we know has_social
          vscode.postMessage({ command: 'fetchExperimentInfo' });
          break;

        case 'experimentInfo':
          actions.setExperimentInfo(message.data);
          vscode.postMessage({ command: 'fetchTimeline' });
          vscode.postMessage({ command: 'fetchAgentProfiles' });
          if (message.data.has_social) {
            vscode.postMessage({ command: 'fetchSocialNetwork' });
          }
          break;

        case 'timeline':
          actions.setTimeline(message.data);
          if (message.data.length > 0) {
            actions.setCurrentStep(0);
            // Fetch initial status
            vscode.postMessage({ command: 'fetchAgentStatuses', step: message.data[0].step });
          }
          actions.setInitialized(true);
          actions.setLoading(false);
          break;

        case 'agentProfiles':
          actions.setAgentProfiles(message.data);
          break;

        case 'agentStatuses':
          actions.setAgentStatuses(message.data);
          break;

        case 'agentStatusHistory':
          actions.setAgentStatusHistory(message.data);
          break;

        case 'agentDialogs':
          actions.setSelectedAgentDialogs(message.data);
          break;

        case 'socialProfile':
          actions.setSocialProfile(message.data);
          break;

        case 'socialPosts':
          actions.setSocialPosts(message.data);
          break;

        case 'socialEvents':
          actions.setSocialEvents(message.data);
          break;

        case 'socialActivity':
          actions.setSocialActivityAtStep(message.data);
          break;

        case 'allPosts':
          actions.setAllPosts(message.data);
          break;

        case 'postComments':
          actions.setPostComments(message.postId, message.data);
          break;

        case 'socialNetwork':
          actions.setSocialNetwork(message.data);
          break;

        case 'trajectory':
          actions.setSelectedAgentTrajectory(message.data);
          break;

        case 'dbTables':
          actions.setDbTables(message.data.tables);
          break;

        case 'dbTableContent':
          actions.setDbTableContent({
            tableName: message.tableName,
            columns: message.data.columns,
            rows: message.data.rows,
            total: message.data.total,
          });
          break;

        case 'error':
          actions.setError(message.message);
          actions.setLoading(false);
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Notify extension that we're ready
    vscode.postMessage({ command: 'ready' });

    return () => window.removeEventListener('message', handleMessage);
  }, [vscode, actions]);

  // Fetch agent statuses and social replay slices when step changes.
  React.useEffect(() => {
    if (initialized && timeline.length > 0 && currentStep < timeline.length) {
      const stepNumber = timeline[currentStep].step;
      vscode.postMessage({ command: 'fetchAgentStatuses', step: stepNumber });
      if (state.experimentInfo?.has_social) {
        vscode.postMessage({ command: 'fetchSocialActivity', step: stepNumber });
        vscode.postMessage({ command: 'fetchAllPosts', step: stepNumber });
        if (selectedAgentId != null) {
          vscode.postMessage({ command: 'fetchSocialEvents', agentId: selectedAgentId, step: stepNumber });
        }
      }
    }
  }, [currentStep, initialized, timeline, vscode, state.experimentInfo?.has_social, selectedAgentId]);

  // Fetch agent dialogs, status history, trajectory, and optional social replay data when selected agent changes.
  React.useEffect(() => {
    if (initialized && selectedAgentId !== null) {
      vscode.postMessage({ command: 'fetchAgentDialogs', agentId: selectedAgentId });
      vscode.postMessage({ command: 'fetchAgentStatusHistory', agentId: selectedAgentId });
      vscode.postMessage({ command: 'fetchTrajectory', agentId: selectedAgentId });
      if (state.experimentInfo?.has_social) {
        const stepNumber = timeline.length > 0 && currentStep < timeline.length ? timeline[currentStep].step : undefined;
        vscode.postMessage({ command: 'fetchSocialProfile', agentId: selectedAgentId });
        vscode.postMessage({ command: 'fetchSocialPosts', agentId: selectedAgentId });
        vscode.postMessage({ command: 'fetchSocialEvents', agentId: selectedAgentId, step: stepNumber });
      }
    }
  }, [selectedAgentId, initialized, state.experimentInfo?.has_social, vscode, timeline, currentStep]);

  // Remember if we've ever seen mobility data (so we keep map even when current step has no positions)
  const hasSeenMobilityRef = React.useRef(false);

  // Auto-detect layout mode: 1) MobilitySpace -> map, 2) Social env only -> network, 3) else -> random
  React.useEffect(() => {
    if (!initialized) return;

    let mode: 'map' | 'network' | 'random' = 'random';

    let hasMobility = false;
    for (const status of state.agentStatuses.values()) {
      if (status.lng != null && status.lat != null) {
        hasMobility = true;
        break;
      }
    }
    if (hasMobility) hasSeenMobilityRef.current = true;

    // Priority: map (MobilitySpace) > network (social only) > random. Don't choose network until we have statuses (so we've had a chance to get positions).
    if (hasSeenMobilityRef.current || hasMobility) {
      mode = 'map';
    } else if (state.socialNetwork && state.socialNetwork.nodes.length > 0 && state.agentStatuses.size > 0) {
      mode = 'network';
    } else if (state.socialNetwork && state.socialNetwork.nodes.length > 0) {
      // Wait for agent statuses before deciding (avoid picking network before mobility data arrives)
      return;
    } else {
      mode = 'random';
    }

    if (state.layoutMode !== mode) {
      actions.setLayoutMode(mode);
    }
  }, [initialized, state.agentStatuses, state.socialNetwork, actions, state.layoutMode]);

  // Loading state
  if (loading || !initialized) {
    return (
      <div className="loading-container">
        <div className="loading-spinner" />
        <div>{t('replay.loading')}</div>
        {initData && (
          <div style={{ fontSize: '12px', opacity: 0.7 }}>
            {t('replay.loadingExperiment', { id: initData.experimentId })}
          </div>
        )}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="loading-container">
        <div style={{ fontSize: '48px' }}>⚠️</div>
        <div style={{ color: 'var(--vscode-errorForeground)' }}>{t('replay.errorTitle')}</div>
        <div style={{ fontSize: '12px', maxWidth: '400px', textAlign: 'center' }}>{error}</div>
        <button
          onClick={() => {
            actions.setError(null);
            actions.setLoading(true);
            vscode.postMessage({ command: 'fetchExperimentInfo' });
          }}
          style={{
            marginTop: '16px',
            padding: '8px 16px',
            background: 'var(--vscode-button-background)',
            color: 'var(--vscode-button-foreground)',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          {t('replay.retry')}
        </button>
      </div>
    );
  }

  // Empty state
  if (timeline.length === 0) {
    return (
      <div className="loading-container">
        <div style={{ fontSize: '48px' }}>📭</div>
        <div>{t('replay.noData')}</div>
        <div style={{ fontSize: '12px', opacity: 0.7, maxWidth: '400px', textAlign: 'center' }}>
          {t('replay.noDataHint')}
        </div>
      </div>
    );
  }

  // Main replay UI
  return (
    <div className="replay-container">
      <div className="deck">
        <AgentMap />
      </div>
      <div className="agentsociety-left">
        <AgentDetailPanel />
      </div>
      <div className="agentsociety-right">
        <AgentRightPanel />
      </div>
      <div className="control-progress">
        <TimelinePlayer />
      </div>
    </div>
  );
};
