/**
 * Type definitions for the Replay Webview
 */

/** VSCode API type */
export interface VSCodeAPI {
  postMessage: (message: any) => void;
  getState: () => any;
  setState: (state: any) => void;
}

/** Agent profile information */
export interface AgentProfile {
  id: number;
  name: string;
  profile: Record<string, any>;
}

/** Legacy agent status at a specific step */
export interface AgentStatus {
  id: number;
  step: number;
  t: string;
  lng: number | null;
  lat: number | null;
  action: string | null;
  status: Record<string, any>;
}

/** Legacy dialog record */
export interface AgentDialog {
  id: number;
  agent_id: number;
  step: number;
  t: string;
  type: DialogType;
  speaker: string;
  content: string;
}

/** Dialog types */
export enum DialogType {
  THOUGHT = 0,
}

/** Timeline point */
export interface TimelinePoint {
  step: number;
  t: string;
}

/** Experiment information */
export interface ExperimentInfo {
  hypothesis_id: string;
  experiment_id: string;
  total_steps: number;
  start_time: string | null;
  end_time: string | null;
  agent_count: number;
  has_social?: boolean;
}

/** Legacy social media types kept for compatibility */
export interface SocialUser {
  user_id: number;
  username: string;
  bio?: string | null;
  created_at?: string | null;
  followers_count: number;
  following_count: number;
  posts_count: number;
  profile: Record<string, any>;
}

export interface SocialPost {
  post_id: number;
  author_id: number;
  content: string;
  post_type: string;
  parent_id?: number | null;
  created_at?: string | null;
  likes_count: number;
  reposts_count: number;
  comments_count: number;
  view_count: number;
  tags?: string[];
  topic_category?: string | null;
  step?: number;
}

export interface SocialComment {
  comment_id: number;
  post_id: number;
  author_id: number;
  content: string;
  parent_comment_id?: number | null;
  created_at?: string | null;
  likes_count?: number;
}

export interface SocialEvent {
  event_id: number;
  step: number;
  t?: string | null;
  sender_id: number;
  sender_name: string;
  action: string;
  content?: string | null;
  receiver_id?: number | null;
  receiver_name?: string | null;
  target_id?: number | null;
  target_author_id?: number | null;
  target_author_name?: string | null;
  summary: string;
}

export interface SocialNetworkNode {
  user_id: number;
  username: string;
}

export interface SocialNetworkEdge {
  source: number;
  target: number;
}

export interface SocialNetwork {
  nodes: SocialNetworkNode[];
  edges: SocialNetworkEdge[];
}

export interface PositionPoint {
  step: number;
  t: string;
  lng: number;
  lat: number;
}

/** Map view state */
export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
}

/** Playback state */
export interface PlaybackState {
  isPlaying: boolean;
  speed: number;
  currentStep: number;
}

/** Layout mode for agent visualization */
export type LayoutMode = 'map' | 'random';

export interface ReplayDatasetColumn {
  column_name: string;
  sqlite_type: string;
  logical_type?: string | null;
  analysis_role?: string | null;
  title?: string | null;
  description?: string | null;
  unit?: string | null;
  nullable: boolean;
  enum_values?: any;
  example?: any;
  tags: string[];
}

export interface ReplayDatasetInfo {
  dataset_id: string;
  table_name: string;
  module_name: string;
  kind: string;
  title: string;
  description: string;
  entity_key?: string | null;
  step_key?: string | null;
  time_key?: string | null;
  default_order: string[];
  capabilities: string[];
  version: number;
  created_at: string;
  columns: ReplayDatasetColumn[];
}

export interface ReplayDatasetList {
  datasets: ReplayDatasetInfo[];
}

export interface ReplayDatasetRows {
  dataset_id: string;
  columns: string[];
  rows: Record<string, any>[];
  total: number;
}

export interface ReplayDatasetPanelRef {
  dataset_id: string;
  module_name: string;
  title: string;
}

export interface ReplayPanelSchema {
  agent_profile_dataset?: ReplayDatasetInfo | null;
  agent_state_datasets: ReplayDatasetInfo[];
  env_state_datasets: ReplayDatasetInfo[];
  geo_dataset?: ReplayDatasetInfo | null;
  trajectory_dataset?: ReplayDatasetInfo | null;
  primary_agent_state_dataset_id?: string | null;
  layout_hint: LayoutMode;
  supports_map: boolean;
}

export interface ReplayPosition {
  agent_id: number;
  lng: number | null;
  lat: number | null;
}

export interface ReplayAgentStateAtStep {
  dataset: ReplayDatasetPanelRef;
  rows_by_agent_id: Record<string, Record<string, any>>;
}

export interface ReplayEnvStateAtStep {
  dataset: ReplayDatasetPanelRef;
  row: Record<string, any> | null;
}

export interface ReplayStepBundle {
  step: number;
  t?: string | null;
  layout_hint: LayoutMode;
  positions: ReplayPosition[];
  agent_state_rows: Record<string, ReplayAgentStateAtStep>;
  env_state_rows: Record<string, ReplayEnvStateAtStep>;
}

export interface ReplayAgentStateHistory {
  agent_id: number;
  dataset_id?: string | null;
  rows: Record<string, any>[];
  history_by_dataset: Record<string, Record<string, any>[]>;
}

export interface SocialActivityAtStep {
  step: number;
  highlightedAgentIds: number[];
}

/** Message types from extension to webview */
export type ExtensionMessage =
  | { type: 'init'; data: InitData }
  | { type: 'experimentInfo'; data: ExperimentInfo }
  | { type: 'timeline'; data: TimelinePoint[] }
  | { type: 'agentProfiles'; data: AgentProfile[] }
  | { type: 'panelSchema'; data: ReplayPanelSchema }
  | { type: 'stepBundle'; data: ReplayStepBundle }
  | { type: 'agentStateHistory'; data: ReplayAgentStateHistory }
  | { type: 'replayDatasets'; data: ReplayDatasetList }
  | { type: 'replayDatasetRows'; data: ReplayDatasetRows }
  | { type: 'agentStatuses'; data: AgentStatus[] }
  | { type: 'agentStatusHistory'; data: AgentStatus[] }
  | { type: 'agentDialogs'; data: AgentDialog[] }
  | { type: 'socialProfile'; data: SocialUser }
  | { type: 'socialPosts'; data: SocialPost[] }
  | { type: 'socialEvents'; data: SocialEvent[] }
  | { type: 'socialNetwork'; data: SocialNetwork }
  | { type: 'socialActivity'; data: SocialActivityAtStep }
  | { type: 'allPosts'; data: SocialPost[] }
  | { type: 'postComments'; data: SocialComment[]; postId: number }
  | { type: 'trajectory'; data: PositionPoint[] }
  | { type: 'error'; message: string };

/** Initial data from extension */
export interface InitData {
  workspacePath: string;
  hypothesisId: string;
  experimentId: string;
  backendUrl: string;
}

/** Message types from webview to extension */
export type WebviewMessage =
  | { command: 'ready' }
  | { command: 'fetchExperimentInfo' }
  | { command: 'fetchTimeline' }
  | { command: 'fetchAgentProfiles' }
  | { command: 'fetchPanelSchema' }
  | { command: 'fetchStepBundle'; step: number }
  | { command: 'fetchAgentStateHistory'; agentId: number; datasetId?: string; startStep?: number; endStep?: number; limit?: number }
  | { command: 'fetchReplayDatasets' }
  | { command: 'fetchReplayDatasetRows'; datasetId: string; page?: number; pageSize?: number; step?: number; entityId?: number; startStep?: number; endStep?: number; maxStep?: number; columns?: string[]; descOrder?: boolean; latestPerEntity?: boolean }
  | { command: 'fetchAgentStatuses'; step?: number }
  | { command: 'fetchAgentStatusHistory'; agentId: number }
  | { command: 'fetchAgentDialogs'; agentId: number; dialogType?: DialogType }
  | { command: 'fetchSocialProfile'; agentId: number }
  | { command: 'fetchSocialPosts'; agentId: number }
  | { command: 'fetchSocialEvents'; agentId: number; step?: number }
  | { command: 'fetchSocialNetwork' }
  | { command: 'fetchSocialActivity'; step: number }
  | { command: 'fetchAllPosts'; step?: number }
  | { command: 'fetchPostComments'; postId: number }
  | { command: 'fetchTrajectory'; agentId: number; startStep?: number; endStep?: number }
  | { command: 'selectAgent'; agentId: number | null }
  | { command: 'error'; message: string };
