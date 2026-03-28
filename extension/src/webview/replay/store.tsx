import * as React from 'react';
import type {
  AgentProfile,
  AgentStatus,
  AgentDialog,
  TimelinePoint,
  ExperimentInfo,
  InitData,
  PlaybackState,
  ViewState,
  PositionPoint,
  SocialUser,
  SocialPost,
  SocialComment,
  SocialEvent,
  SocialNetwork,
  SocialActivityAtStep,
  LayoutMode,
  ReplayDatasetInfo,
  ReplayDatasetRows,
} from './types';

/** Replay store state */
export interface ReplayState {
  // Initialization
  initialized: boolean;
  loading: boolean;
  error: string | null;

  // Experiment info
  initData: InitData | null;
  experimentInfo: ExperimentInfo | null;

  // Timeline
  timeline: TimelinePoint[];
  currentStep: number;
  playback: PlaybackState;

  // Layout
  layoutMode: LayoutMode;

  // Agent data
  agentProfiles: Map<number, AgentProfile>;
  agentStatuses: Map<number, AgentStatus>; // Current step statuses
  /** Full status history for the selected agent (all steps) */
  agentStatusHistory: AgentStatus[];
  selectedAgentId: number | null;
  selectedAgentDialogs: AgentDialog[];
  selectedAgentTrajectory: PositionPoint[];
  socialProfile: SocialUser | null;
  socialPosts: SocialPost[];
  socialEvents: SocialEvent[];
  socialNetwork: SocialNetwork | null;
  /** Per-step social activity derived from social replay events. */
  socialActivityAtStep: SocialActivityAtStep | null;
  /** All posts up to current step (timeline); for 帖子 panel */
  allPosts: SocialPost[];
  /** Comments by post_id for post detail modal */
  postCommentsMap: Record<number, SocialComment[]>;

  // Database data
  replayDatasets: ReplayDatasetInfo[];
  replayDatasetRows: ReplayDatasetRows | null;

  // Map
  viewState: ViewState;

}

/** Replay store actions */
export interface ReplayActions {
  setInitData: (data: InitData) => void;
  setExperimentInfo: (info: ExperimentInfo) => void;
  setTimeline: (timeline: TimelinePoint[]) => void;
  setAgentProfiles: (profiles: AgentProfile[]) => void;
  setAgentStatuses: (statuses: AgentStatus[]) => void;
  setAgentStatusHistory: (history: AgentStatus[]) => void;
  setCurrentStep: (step: number) => void;
  selectAgent: (agentId: number | null) => void;
  setSelectedAgentDialogs: (dialogs: AgentDialog[]) => void;
  setSelectedAgentTrajectory: (trajectory: PositionPoint[]) => void;
  setSocialProfile: (profile: SocialUser | null) => void;
  setSocialPosts: (posts: SocialPost[]) => void;
  setSocialEvents: (events: SocialEvent[]) => void;
  setSocialNetwork: (network: SocialNetwork | null) => void;
  setSocialActivityAtStep: (activity: SocialActivityAtStep | null) => void;
  setAllPosts: (posts: SocialPost[]) => void;
  setPostComments: (postId: number, comments: SocialComment[]) => void;
  setReplayDatasets: (datasets: ReplayDatasetInfo[]) => void;
  setReplayDatasetRows: (rows: ReplayDatasetRows | null) => void;
  setViewState: (viewState: Partial<ViewState>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setInitialized: (initialized: boolean) => void;

  // Playback controls
  play: () => void;
  pause: () => void;
  nextStep: () => void;
  prevStep: () => void;
  setPlaybackSpeed: (speed: number) => void;
  setLayoutMode: (mode: LayoutMode) => void;
}

/** Initial state */
const initialState: ReplayState = {
  initialized: false,
  loading: true,
  error: null,

  initData: null,
  experimentInfo: null,

  timeline: [],
  currentStep: 0,
  playback: {
    isPlaying: false,
    speed: 1000,
    currentStep: 0,
  },

  layoutMode: 'map', // Default to map, will be auto-detected

  agentProfiles: new Map(),
  agentStatuses: new Map(),
  agentStatusHistory: [],
  selectedAgentId: null,
  selectedAgentDialogs: [],
  selectedAgentTrajectory: [],
  socialProfile: null,
  socialPosts: [],
  socialEvents: [],
  socialNetwork: null,
  socialActivityAtStep: null,
  allPosts: [],
  postCommentsMap: {},
  replayDatasets: [],
  replayDatasetRows: null,

  viewState: {
    longitude: 116.4,
    latitude: 39.9,
    zoom: 12,
    pitch: 0,
    bearing: 0,
  },
};

/** Combined context type */
export interface ReplayContextType {
  state: ReplayState;
  actions: ReplayActions;
  sendMessage: (message: any) => void;
}

/** Create context */
const ReplayContext = React.createContext<ReplayContextType | null>(null);

/** Provider component */
export interface ReplayProviderProps {
  children: React.ReactNode;
  vscode: any;
}

export const ReplayProvider: React.FC<ReplayProviderProps> = ({ children, vscode }) => {
  const [state, setState] = React.useState<ReplayState>(initialState);
  const playbackTimerRef = React.useRef<NodeJS.Timeout | null>(null);

  // Create actions
  const actions: ReplayActions = React.useMemo(() => ({
    setInitData: (data) => setState((s) => ({ ...s, initData: data })),

    setExperimentInfo: (info) => setState((s) => ({ ...s, experimentInfo: info })),

    setTimeline: (timeline) => setState((s) => ({ ...s, timeline })),

    setAgentProfiles: (profiles) => {
      const map = new Map<number, AgentProfile>();
      profiles.forEach((p) => map.set(p.id, p));
      setState((s) => ({ ...s, agentProfiles: map }));
    },

    setAgentStatuses: (statuses) => {
      const map = new Map<number, AgentStatus>();
      statuses.forEach((status) => map.set(status.id, status));
      setState((s) => ({ ...s, agentStatuses: map }));
    },

    setAgentStatusHistory: (history: AgentStatus[]) => setState((s) => ({ ...s, agentStatusHistory: history })),

    setCurrentStep: (step) => {
      setState((s) => ({
        ...s,
        currentStep: step,
        playback: { ...s.playback, currentStep: step },
      }));
    },

    selectAgent: (agentId) => {
      setState((s) => ({
        ...s,
        selectedAgentId: agentId,
        agentStatusHistory: [], // cleared on selection change; filled when fetchAgentStatusHistory returns
        selectedAgentDialogs: [],
        selectedAgentTrajectory: [],
        socialProfile: null,
        socialPosts: [],
        socialEvents: [],
      }));
    },

    setSelectedAgentDialogs: (dialogs) => setState((s) => ({ ...s, selectedAgentDialogs: dialogs })),

    setSelectedAgentTrajectory: (trajectory) => setState((s) => ({ ...s, selectedAgentTrajectory: trajectory })),

    setSocialProfile: (profile) => setState((s) => ({ ...s, socialProfile: profile })),

    setSocialPosts: (posts) => setState((s) => ({ ...s, socialPosts: posts })),

    setSocialEvents: (events) => setState((s) => ({ ...s, socialEvents: events })),

    setSocialNetwork: (network) => setState((s) => ({ ...s, socialNetwork: network })),

    setSocialActivityAtStep: (activity) => setState((s) => ({ ...s, socialActivityAtStep: activity })),

    setAllPosts: (posts: SocialPost[]) => setState((s) => ({ ...s, allPosts: posts })),

    setPostComments: (postId: number, comments: SocialComment[]) =>
      setState((s) => ({ ...s, postCommentsMap: { ...s.postCommentsMap, [postId]: comments } })),

    setReplayDatasets: (datasets) => setState((s) => ({ ...s, replayDatasets: datasets })),

    setReplayDatasetRows: (rows) => setState((s) => ({ ...s, replayDatasetRows: rows })),

    setViewState: (viewState) =>
      setState((s) => ({ ...s, viewState: { ...s.viewState, ...viewState } })),

    setLoading: (loading) => setState((s) => ({ ...s, loading })),

    setError: (error) => setState((s) => ({ ...s, error })),

    setInitialized: (initialized) => setState((s) => ({ ...s, initialized })),

    play: () => {
      setState((s) => ({
        ...s,
        playback: { ...s.playback, isPlaying: true },
      }));
    },

    pause: () => {
      setState((s) => ({
        ...s,
        playback: { ...s.playback, isPlaying: false },
      }));
    },

    nextStep: () => {
      setState((s) => {
        const nextIdx = Math.min(s.currentStep + 1, s.timeline.length - 1);
        return {
          ...s,
          currentStep: nextIdx,
          playback: { ...s.playback, currentStep: nextIdx },
        };
      });
    },

    prevStep: () => {
      setState((s) => {
        const prevIdx = Math.max(s.currentStep - 1, 0);
        return {
          ...s,
          currentStep: prevIdx,
          playback: { ...s.playback, currentStep: prevIdx },
        };
      });
    },

    setPlaybackSpeed: (speed) => {
      setState((s) => ({
        ...s,
        playback: { ...s.playback, speed },
      }));
    },

    setLayoutMode: (mode) => {
      setState((s) => ({ ...s, layoutMode: mode }));
    },
  }), []);

  // Handle playback timer
  React.useEffect(() => {
    if (state.playback.isPlaying) {
      playbackTimerRef.current = setInterval(() => {
        setState((s) => {
          const nextIdx = s.currentStep + 1;
          if (nextIdx >= s.timeline.length) {
            // Stop at the end
            return {
              ...s,
              playback: { ...s.playback, isPlaying: false },
            };
          }
          return {
            ...s,
            currentStep: nextIdx,
            playback: { ...s.playback, currentStep: nextIdx },
          };
        });
      }, state.playback.speed);
    } else {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    }

    return () => {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    };
  }, [state.playback.isPlaying, state.playback.speed]);

  const sendMessage = React.useCallback((message: any) => {
    vscode.postMessage(message);
  }, [vscode]);

  const contextValue = React.useMemo(() => ({ state, actions, sendMessage }), [state, actions, sendMessage]);

  return (
    <ReplayContext.Provider value={contextValue}>
      {children}
    </ReplayContext.Provider>
  );
};

/** Hook to use replay context */
export const useReplay = (): ReplayContextType => {
  const context = React.useContext(ReplayContext);
  if (!context) {
    throw new Error('useReplay must be used within a ReplayProvider');
  }
  return context;
};
