/**
 * Replay App - Main component for simulation replay
 */

import * as React from 'react';
import { ConfigProvider } from 'antd';
import { useTranslation } from 'react-i18next';
import type { ExtensionMessage, VSCodeAPI } from './types';
import { ReplayProvider, useReplay } from './store';
import { TimelinePlayer, AgentDetailPanel, AgentMap, AgentRightPanel } from './components';
import { useVscodeTheme } from '../theme';

interface ReplayAppProps {
  vscode: VSCodeAPI;
}

export const ReplayApp: React.FC<ReplayAppProps> = ({ vscode }) => {
  const { themeConfig } = useVscodeTheme();

  return (
    <ConfigProvider theme={themeConfig}>
      <ReplayProvider vscode={vscode}>
        <ReplayAppInner vscode={vscode} />
      </ReplayProvider>
    </ConfigProvider>
  );
};

const ReplayAppInner: React.FC<ReplayAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const {
    initialized,
    loading,
    error,
    initData,
    currentStep,
    timeline,
  } = state;

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent<ExtensionMessage>) => {
      const message = event.data;

      switch (message.type) {
        case 'init':
          actions.setInitData(message.data);
          actions.setLoading(true);
          vscode.postMessage({ command: 'fetchExperimentInfo' });
          vscode.postMessage({ command: 'fetchTimeline' });
          vscode.postMessage({ command: 'fetchAgentProfiles' });
          vscode.postMessage({ command: 'fetchPanelSchema' });
          break;

        case 'experimentInfo':
          actions.setExperimentInfo(message.data);
          break;

        case 'timeline':
          actions.setTimeline(message.data);
          actions.setInitialized(true);
          actions.setLoading(false);
          if (message.data.length > 0) {
            actions.setCurrentStep(0);
          }
          break;

        case 'agentProfiles':
          actions.setAgentProfiles(message.data);
          break;

        case 'panelSchema':
          actions.setPanelSchema(message.data);
          break;

        case 'stepBundle':
          actions.setStepBundle(message.data);
          break;

        case 'replayDatasetRows':
          actions.setReplayDatasetRows(message.requestKey ?? 'default', message.data);
          break;

        case 'error':
          actions.setError(message.message);
          actions.setLoading(false);
          break;

        default:
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    vscode.postMessage({ command: 'ready' });
    return () => window.removeEventListener('message', handleMessage);
  }, [vscode, actions]);

  React.useEffect(() => {
    if (!initialized || timeline.length === 0 || currentStep >= timeline.length) {
      return;
    }
    const stepNumber = timeline[currentStep]?.step;
    if (stepNumber === undefined) {
      return;
    }
    vscode.postMessage({ command: 'fetchStepBundle', step: stepNumber });
  }, [currentStep, initialized, timeline, vscode]);

  if (error) {
    return (
      <div className="loading-container">
        <div style={{ fontSize: '48px' }}>⚠️</div>
        <div style={{ color: 'var(--vscode-errorForeground)' }}>{t('replay.errorTitle')}</div>
        <div style={{ fontSize: '12px', maxWidth: '400px', textAlign: 'center' }}>{error}</div>
      </div>
    );
  }

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
