/**
 * Agent List Component
 * Displays list of agents with their current status
 */

import * as React from 'react';
import { useReplay } from '../store';

export const AgentList: React.FC = () => {
  const { state, actions } = useReplay();
  const { agentProfiles, agentStatuses, selectedAgentId } = state;

  // Sort agents by ID
  const sortedAgents = React.useMemo(() => {
    return Array.from(agentProfiles.values()).sort((a, b) => a.id - b.id);
  }, [agentProfiles]);

  const handleAgentClick = (agentId: number) => {
    actions.selectAgent(agentId === selectedAgentId ? null : agentId);
  };

  return (
    <div className="agent-list">
      {sortedAgents.map((agent) => {
        const status = agentStatuses.get(agent.id);
        const isSelected = agent.id === selectedAgentId;

        // Get initials for avatar
        const initials = agent.name
          .split(' ')
          .map((n) => n[0])
          .join('')
          .slice(0, 2)
          .toUpperCase();

        return (
          <div
            key={agent.id}
            className={`agent-item ${isSelected ? 'selected' : ''}`}
            onClick={() => handleAgentClick(agent.id)}
          >
            <div className="agent-avatar">{initials}</div>
            <div className="agent-info">
              <div className="agent-name">{agent.name}</div>
              <div className="agent-action">
                {status?.action || status?.status?.thought || 'No activity'}
              </div>
            </div>
          </div>
        );
      })}

      {sortedAgents.length === 0 && (
        <div style={{ padding: '16px', textAlign: 'center', color: 'var(--vscode-descriptionForeground)' }}>
          No agents found
        </div>
      )}
    </div>
  );
};
