/**
 * Type definitions for the Replay Webview
 */

import type { Dayjs } from 'dayjs';

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

/** Agent status at a specific step */
export interface AgentStatus {
  id: number;
  step: number;
  t: string; // ISO datetime string
  lng: number | null;
  lat: number | null;
  action: string | null;
  status: {
    satisfactions?: Record<string, number>;
    emotion?: Record<string, number>;
    emotion_type?: string;
    thought?: string;
    need?: Record<string, any>;
    intention?: Record<string, any>;
    plan?: {
      target: string;
      index: number;
      completed: boolean;
      failed: boolean;
      steps: Array<{
        intention: string;
        status: string;
      }>;
    };
  };
}

/** Agent dialog record */
export interface AgentDialog {
  id: number;
  agent_id: number;
  step: number;
  t: string; // ISO datetime string
  type: DialogType;
  speaker: string;
  content: string;
}

/** Dialog types */
export enum DialogType {
  THOUGHT = 0,       // 思考/反思
}

/** Timeline point */
export interface TimelinePoint {
  step: number;
  t: string; // ISO datetime string
}

/** Experiment information */
export interface ExperimentInfo {
  hypothesis_id: string;
  experiment_id: string;
  total_steps: number;
  start_time: string | null;
  end_time: string | null;
  agent_count: number;
  /** Whether the experiment has social module (social_user table). When false, do not request social APIs or show social panel. */
  has_social?: boolean;
}

// Metric removed

/** Social media user profile */
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

/** Social media post */
export interface SocialPost {
  post_id: number;
  author_id?: number; // optional for backward compat
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

/** Social media comment on a post */
export interface SocialComment {
  comment_id: number;
  post_id: number;
  author_id: number;
  content: string;
  parent_comment_id?: number | null;
  created_at?: string | null;
  likes_count?: number;
}

/** Social media direct message */
export interface SocialDirectMessage {
  message_id: number;
  from_user_id: number;
  to_user_id: number;
  content: string;
  created_at?: string | null;
  read: boolean;
}

/** Social media group message */
export interface SocialGroupMessage {
  message_id: number;
  group_id: number;
  group_name?: string | null;
  from_user_id: number;
  content: string;
  created_at?: string | null;
}

/** Social network graph */
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

/** Position data for trajectory */
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
  speed: number; // ms per step
  currentStep: number;
}

/** Layout mode for agent visualization */
export type LayoutMode = 'map' | 'network' | 'random';

/** Database table list */
export interface TableList {
  tables: string[];
}

/** Database table content */
export interface TableContent {
  columns: string[];
  rows: Record<string, any>[];
  total: number;
}

/** Per-step social activity: which agents received/sent DMs or sent group messages */
export interface SocialActivityAtStep {
  step: number;
  receivedDmAgentIds: number[];
  sentDmAgentIds: number[];
  sentGroupMessageAgentIds: number[];
}

/** Message types from extension to webview */
export type ExtensionMessage =
  | { type: 'init'; data: InitData }
  | { type: 'experimentInfo'; data: ExperimentInfo }
  | { type: 'timeline'; data: TimelinePoint[] }
  | { type: 'agentProfiles'; data: AgentProfile[] }
  | { type: 'agentStatuses'; data: AgentStatus[] }
  | { type: 'agentStatusHistory'; data: AgentStatus[] }
  | { type: 'agentDialogs'; data: AgentDialog[] }
  | { type: 'socialProfile'; data: SocialUser }
  | { type: 'socialPosts'; data: SocialPost[] }
  | { type: 'socialDirectMessages'; data: SocialDirectMessage[] }
  | { type: 'socialGroupMessages'; data: SocialGroupMessage[] }
  | { type: 'socialNetwork'; data: SocialNetwork }
  | { type: 'socialActivity'; data: SocialActivityAtStep }
  | { type: 'allPosts'; data: SocialPost[] }
  | { type: 'postComments'; data: SocialComment[]; postId: number }
  | { type: 'trajectory'; data: PositionPoint[] }
  | { type: 'dbTables'; data: TableList }
  | { type: 'dbTableContent'; data: TableContent; tableName: string }
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
  | { command: 'fetchAgentStatuses'; step?: number }
  | { command: 'fetchAgentStatusHistory'; agentId: number }
  | { command: 'fetchAgentDialogs'; agentId: number; dialogType?: DialogType }
  | { command: 'fetchSocialProfile'; agentId: number }
  | { command: 'fetchSocialPosts'; agentId: number }
  | { command: 'fetchSocialDirectMessages'; agentId: number; step?: number }
  | { command: 'fetchSocialGroupMessages'; agentId: number; step?: number }
  | { command: 'fetchSocialNetwork' }
  | { command: 'fetchSocialActivity'; step: number }
  | { command: 'fetchAllPosts'; step?: number }
  | { command: 'fetchPostComments'; postId: number }
  | { command: 'fetchTrajectory'; agentId: number; startStep?: number; endStep?: number }
  | { command: 'fetchDbTables' }
  | { command: 'fetchDbTableContent'; tableName: string; page?: number; pageSize?: number }
  | { command: 'selectAgent'; agentId: number | null }
  | { command: 'error'; message: string };
