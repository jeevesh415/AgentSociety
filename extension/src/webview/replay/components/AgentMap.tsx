/**
 * AgentMap Component - Interactive map visualization using DeckGL and Mapbox
 */

import * as React from 'react';
import { useTranslation } from 'react-i18next';
import MapGL from 'react-map-gl';
import mapboxgl from 'mapbox-gl';
// @ts-ignore - Mapbox CSP worker type definition may be missing
import MapboxWorker from 'mapbox-gl/dist/mapbox-gl-csp-worker';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, PathLayer, IconLayer, TextLayer, LineLayer } from '@deck.gl/layers';
import { OrthographicView } from '@deck.gl/core';
import { useReplay } from '../store';
import 'mapbox-gl/dist/mapbox-gl.css';

// Mapbox token
const MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiZmh5ZHJhbGlzayIsImEiOiJja3VzMWc5NXkwb3RnMm5sbnVvd3IydGY0In0.FrwFkYIMpLbU83K9rHSe8w';
const MAP_STYLE = 'mapbox://styles/mapbox/standard';

const resolvedWorker = (MapboxWorker as any).default ?? MapboxWorker;
if (typeof resolvedWorker === 'string') {
  mapboxgl.workerUrl = resolvedWorker;
} else if (typeof resolvedWorker === 'function') {
  if (typeof (mapboxgl as any).setWorkerClass === 'function') {
    (mapboxgl as any).setWorkerClass(resolvedWorker);
  } else {
    mapboxgl.workerClass = resolvedWorker;
  }
}

// Default view state for Beijing area
const INITIAL_VIEW_STATE = {
  longitude: 116.4,
  latitude: 39.9,
  zoom: 10.5,
  pitch: 0,
  bearing: 0,
};

// Get icon URIs from window (injected by ReplayWebviewProvider) or use bundled PNGs
declare global {
  interface Window {
    __AGENT_ICON_URIS__?: Record<string, string>;
  }
}

import { AGENT_ICONS, getAgentIconUrl } from '../icons';

const getIconUris = () => {
  const injected = window.__AGENT_ICON_URIS__;
  // Use injected URIs if available and have content, otherwise use bundled PNGs
  if (injected && Object.keys(injected).length > 0) {
    console.log('[AgentMap] Using injected icon URIs');
    return injected;
  }
  return AGENT_ICONS;
};

// Get avatar URL based on agent profile (gender + age)
function getAvatarUrl(profile: Record<string, any> | undefined): string {
  const icons = getIconUris();
  return getAgentIconUrl(profile) || icons.agent || '';
}

// Get color based on agent profile for ScatterplotLayer fallback
function getAgentColor(profile: Record<string, any> | undefined): [number, number, number, number] {
  if (!profile) return [22, 119, 255, 255];
  const gender = profile.gender?.toLowerCase();
  const age = profile.age;

  if (gender === 'male') return [66, 165, 245, 255];
  if (gender === 'female') return [206, 147, 216, 255];
  if (typeof age === 'number' && age < 35) return [66, 165, 245, 255];

  return [22, 119, 255, 255];
}

const INITIAL_ORTHO_VIEW_STATE = {
  target: [0, 0, 0] as [number, number, number],
  zoom: 1,
};

// Deterministic random layout based on ID
function getRandomLayout(ids: number[], count: number): Map<number, [number, number]> {
  const positions = new Map<number, [number, number]>();
  ids.forEach((id) => {
    const seed = id * 9301 + 49297;
    const x = ((seed % 1000) / 1000 - 0.5) * 200;
    const y = (((seed * 123) % 1000) / 1000 - 0.5) * 200;
    positions.set(id, [x, y]);
  });
  return positions;
}

// Simple force-directed layout
function getNetworkLayout(nodes: number[], edges: { source: number, target: number }[]): Map<number, [number, number]> {
  const positions = new Map<number, [number, number]>();
  // Increase initial spread
  const spread = 2000;
  nodes.forEach(id => {
    const seed = id * 9301 + 49297;
    positions.set(id, [((seed % 1000) / 1000 - 0.5) * spread, (((seed * 123) % 1000) / 1000 - 0.5) * spread]);
  });

  if (nodes.length === 0) return positions;

  const iterations = 80;
  const k = 600; // Increased ideal length
  const repulsion = 2000000; // Significantly increased repulsion

  for (let i = 0; i < iterations; i++) {
    const disp = new Map<number, [number, number]>();
    nodes.forEach(id => disp.set(id, [0, 0]));

    // Repulsion
    for (let u of nodes) {
      for (let v of nodes) {
        if (u === v) continue;
        const posU = positions.get(u)!;
        const posV = positions.get(v)!;
        const dx = posU[0] - posV[0];
        const dy = posU[1] - posV[1];
        const distSq = dx * dx + dy * dy;

        // Soft minimal distance to avoid explosion
        const effectiveDistSq = Math.max(distSq, 100);
        const dist = Math.sqrt(effectiveDistSq);
        const f = repulsion / effectiveDistSq;

        const d = disp.get(u)!;
        d[0] += (dx / dist) * f;
        d[1] += (dy / dist) * f;
      }
    }

    // Attraction
    for (let edge of edges) {
      const u = edge.source;
      const v = edge.target;
      if (!positions.has(u) || !positions.has(v)) continue;

      const posU = positions.get(u)!;
      const posV = positions.get(v)!;
      const dx = posU[0] - posV[0];
      const dy = posU[1] - posV[1];
      const dist = Math.sqrt(dx * dx + dy * dy);

      const f = (dist * dist) / k;
      if (dist > 0) {
        const dU = disp.get(u)!;
        const dV = disp.get(v)!;
        dU[0] -= (dx / dist) * f;
        dU[1] -= (dy / dist) * f;
        dV[0] += (dx / dist) * f;
        dV[1] += (dy / dist) * f;
      }
    }

    // Apply
    nodes.forEach(id => {
      const pos = positions.get(id)!;
      const d = disp.get(id)!;
      // const len = Math.sqrt(d[0] * d[0] + d[1] * d[1]);
      // Limit speed dampening
      const limit = 50 * (1 - i / iterations); // Cool down
      const lenSq = d[0] * d[0] + d[1] * d[1];
      const len = Math.sqrt(lenSq);

      if (len > 0) {
        const scale = Math.min(len, limit) / len;
        pos[0] += d[0] * scale;
        pos[1] += d[1] * scale;
      }
    });
  }

  return positions;
}

interface AgentMapProps {
  mapboxToken?: string;
}

export const AgentMap: React.FC<AgentMapProps> = ({ mapboxToken = MAPBOX_ACCESS_TOKEN }) => {
  const { t } = useTranslation();
  const { state, actions } = useReplay();
  const { agentProfiles, agentStatuses, selectedAgentId, socialNetwork, socialActivityAtStep, layoutMode } = state;
  const [geoViewState, setGeoViewState] = React.useState(INITIAL_VIEW_STATE);
  const [orthoViewState, setOrthoViewState] = React.useState(INITIAL_ORTHO_VIEW_STATE);
  const [hovering, setHovering] = React.useState(false);
  const [isInitialized, setIsInitialized] = React.useState(false);
  const [mapError, setMapError] = React.useState<string | null>(null);
  const [blinkPhase, setBlinkPhase] = React.useState(0);

  // Blink animation for agents highlighted by social interactions at this step.
  const hasSocialHighlights = (socialActivityAtStep?.highlightedAgentIds?.length ?? 0) > 0;
  React.useEffect(() => {
    if (!hasSocialHighlights) return;
    let raf = 0;
    const start = performance.now();
    const tick = () => {
      const t = (performance.now() - start) / 600;
      setBlinkPhase((t * Math.PI * 2) % (Math.PI * 2));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [hasSocialHighlights]);

  // Memoize layouts
  const randomLayout = React.useMemo(() => {
    return getRandomLayout(Array.from(agentProfiles.keys()), agentProfiles.size);
  }, [agentProfiles]);

  const networkLayout = React.useMemo(() => {
    if (!socialNetwork) return new Map();
    const nodes = socialNetwork.nodes.map(n => n.user_id);
    const edges = socialNetwork.edges.map(e => ({ source: e.source, target: e.target }));
    return getNetworkLayout(nodes, edges);
  }, [socialNetwork]);

  // Update logic to maintain separate view states and switch interactions
  const viewState = layoutMode === 'map' ? geoViewState : orthoViewState;

  const handleViewStateChange = ({ viewState: nextViewState }: any) => {
    if (layoutMode === 'map') {
      setGeoViewState(nextViewState);
    } else {
      setOrthoViewState(nextViewState);
    }
  };

  // Prepare agent data for visualization


  // Prepare agent data for visualization
  const agentList = React.useMemo(() => {
    const data: Array<{
      id: number;
      name: string;
      lng: number; // Used as X in Cartesian
      lat: number; // Used as Y in Cartesian
      avatarUrl: string;
      profile: Record<string, any> | undefined;
    }> = [];

    const ids = Array.from(agentProfiles.keys());
    agentStatuses.forEach((status, id) => {
      let x = 0, y = 0;
      let visible = false;

      if (layoutMode === 'map') {
        if (status.lng != null && status.lat != null) {
          x = status.lng;
          y = status.lat;
          visible = true;
        }
      } else if (layoutMode === 'network') {
        const pos = networkLayout.get(id);
        if (pos) {
          x = pos[0];
          y = pos[1];
          visible = true;
        } else if (randomLayout.has(id)) {
          // Fallback to random if not in network?
          const rPos = randomLayout.get(id)!;
          x = rPos[0];
          y = rPos[1];
          visible = true;
        }
      } else { // random
        const pos = randomLayout.get(id);
        if (pos) {
          x = pos[0];
          y = pos[1];
          visible = true;
        }
      }

      if (visible) {
        const profile = agentProfiles.get(id);
        data.push({
          id,
          name: profile?.name || `Agent ${id}`,
          lng: x,
          lat: y,
          avatarUrl: getAvatarUrl(profile?.profile),
          profile: profile?.profile,
        });
      }
    });

    return data;
  }, [agentStatuses, agentProfiles, layoutMode, randomLayout, networkLayout]);

  // Auto-fit view to agent positions on first load (simplified)
  React.useEffect(() => {
    // Only fit for map mode initially to avoid jumping
    if (!isInitialized && agentList.length > 0 && layoutMode === 'map') {
      const lngs = agentList.map(a => a.lng);
      const lats = agentList.map(a => a.lat);
      const minLng = Math.min(...lngs);
      const maxLng = Math.max(...lngs);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const centerLng = (minLng + maxLng) / 2;
      const centerLat = (minLat + maxLat) / 2;

      setGeoViewState(prev => ({
        ...prev,
        longitude: centerLng,
        latitude: centerLat,
        zoom: 10.5,
      }));
      setIsInitialized(true);
    }
  }, [agentList, isInitialized, layoutMode]);

  // Build layers based on zoom level (and mode)
  const layers = React.useMemo(() => {
    const result: any[] = [];
    const isCartesian = layoutMode !== 'map';
    // Use orthoViewState.zoom or geoViewState.zoom
    const currentZoom = isCartesian ? orthoViewState.zoom : geoViewState.zoom;

    // Add Edges for Network Mode
    if (layoutMode === 'network' && socialNetwork) {
      // Since networkLayout is id -> [x, y]
      const edges = socialNetwork.edges.map(e => {
        const sourcePos = networkLayout.get(e.source);
        const targetPos = networkLayout.get(e.target);
        if (!sourcePos || !targetPos) return null;
        return {
          sourcePosition: sourcePos,
          targetPosition: targetPos,
        };
      }).filter(Boolean);

      result.push(new LineLayer({
        id: 'agent-edges',
        data: edges,
        getSourcePosition: (d: any) => d.sourcePosition,
        getTargetPosition: (d: any) => d.targetPosition,
        getColor: [150, 150, 150, 100],
        getWidth: 1,
        widthMinPixels: 1,
        parameters: { depthTest: false },
      }));
    }

    const showIcons = isCartesian ? currentZoom > 0.5 : currentZoom > 10;

    if (showIcons) {
      const icons = getIconUris();
      const hasIcons = Object.keys(icons).length > 0;

      if (hasIcons) {
        // IconLayer
        result.push(new IconLayer({
          id: 'agent-icons',
          data: agentList.map(a => ({
            id: a.id,
            coordinate: [a.lng, a.lat],
            avatarUrl: a.avatarUrl,
            isSelected: a.id === selectedAgentId,
          })),
          pickable: true,
          billboard: true,
          getIcon: (d: any) => ({
            url: d.avatarUrl,
            width: 128,
            height: 128,
            anchorX: 64,
            anchorY: 64,
          }),
          getSize: (d: any) => d.isSelected ? 40 : 32,
          getPosition: (d: any) => d.coordinate,
          sizeScale: 1,
          sizeMinPixels: 24,
          sizeMaxPixels: 56,
          parameters: {
            depthTest: false,
          },
        }));
        // Highlight agents that were targeted by social interactions at this step.
        if (socialActivityAtStep?.highlightedAgentIds?.length) {
          const highlightedAgents = agentList.filter(a => socialActivityAtStep.highlightedAgentIds.includes(a.id));
          if (highlightedAgents.length > 0) {
            const outlineAlpha = Math.round(100 + 155 * (0.5 + 0.5 * Math.sin(blinkPhase)));
            result.push(new ScatterplotLayer({
              id: 'social-highlighted-agents',
              data: highlightedAgents.map(a => ({ id: a.id, position: [a.lng, a.lat] })),
              pickable: false,
              getPosition: (d: any) => d.position,
              getRadius: isCartesian ? 20 : 8,
              radiusUnits: isCartesian ? 'pixels' : 'meters',
              radiusScale: isCartesian ? 1 : 1,
              getFillColor: [255, 80, 80, 0],
              getLineColor: [255, 80, 80, outlineAlpha],
              getLineWidth: 4,
              stroked: true,
              filled: false,
              radiusMinPixels: 18,
              radiusMaxPixels: 28,
              parameters: { depthTest: false },
            }));
          }
        }
      } else {
        result.push(new ScatterplotLayer({
          id: 'agent-circles',
          data: agentList.map(a => ({
            id: a.id,
            position: [a.lng, a.lat],
            color: a.id === selectedAgentId ? [255, 0, 0, 255] : getAgentColor(a.profile),
            radius: a.id === selectedAgentId ? 18 : 14,
          })),
          pickable: true,
          stroked: true,
          filled: true,
          lineWidthMinPixels: 2,
          lineWidthMaxPixels: 4,
          getPosition: (d: any) => d.position,
          radiusUnits: isCartesian ? 'pixels' : 'meters',
          radiusScale: isCartesian ? 1 : 1,
          getRadius: (d: any) => d.radius,
          getFillColor: (d: any) => d.color,
          getLineColor: [255, 255, 255, 220],
          getLineWidth: 3,
          radiusMinPixels: 12,
          radiusMaxPixels: 24,
        }));
        // Highlight agents that were targeted by social interactions at this step.
        if (socialActivityAtStep?.highlightedAgentIds?.length) {
          const highlightedAgents = agentList.filter(a => socialActivityAtStep.highlightedAgentIds.includes(a.id));
          if (highlightedAgents.length > 0) {
            result.push(new ScatterplotLayer({
              id: 'social-highlighted-agents',
              data: highlightedAgents.map(a => ({ id: a.id, position: [a.lng, a.lat] })),
              pickable: false,
              getPosition: (d: any) => d.position,
              getRadius: isCartesian ? 22 : 10,
              radiusUnits: isCartesian ? 'pixels' : 'meters',
              radiusScale: isCartesian ? 1 : 1,
              getFillColor: [255, 80, 80, 100],
              getLineColor: [255, 60, 60, 255],
              getLineWidth: 3,
              stroked: true,
              filled: true,
              radiusMinPixels: 20,
              radiusMaxPixels: 30,
              parameters: { depthTest: false },
            }));
          }
        }
      }

      // TextLayer: fixed pixel size for name labels, same on map / network / random
      const textSizePixels = 12;
      result.push(new TextLayer({
        id: 'text',
        data: agentList.filter(a => a.name).map(a => ({
          id: a.id,
          position: [a.lng, a.lat],
          text: a.name,
        })),
        background: true,
        backgroundPadding: [4, 4, 4, 4],
        characterSet: 'auto',
        fontFamily: 'system-ui',
        getText: d => d.text,
        getPosition: d => d.position,
        getSize: textSizePixels,
        sizeUnits: 'pixels',
        sizeScale: 1,
        getBackgroundColor: [0, 0, 0, 128],
        getColor: [255, 255, 255],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'bottom',
        getPixelOffset: [0, -20],
        parameters: { depthTest: false },
      }));

    } else {
      // Low zoom Scatterplot
      result.push(new ScatterplotLayer({
        id: 'point',
        data: agentList.map(a => ({
          id: a.id,
          position: [a.lng, a.lat],
          radius: 10,
          color: a.id === selectedAgentId ? [255, 0, 0] : [22, 119, 255],
        })),
        pickable: true,
        radiusUnits: isCartesian ? 'pixels' : 'meters',
        radiusScale: isCartesian ? 1 : 20,
        radiusMinPixels: 1,
        radiusMaxPixels: 100,
        getPosition: d => d.position,
        getRadius: d => d.radius,
        getFillColor: d => d.color,
      }));
    }

    // No PathLayer (Trajectory removed)

    return result;
  }, [agentList, geoViewState.zoom, orthoViewState.zoom, selectedAgentId, layoutMode, socialActivityAtStep, blinkPhase]);

  // Handle click on agent
  const handleClick = React.useCallback((info: any) => {
    if (info.object) {
      const agentId = info.object.id;
      actions.selectAgent(agentId === selectedAgentId ? null : agentId);
    }
  }, [actions, selectedAgentId]);

  if (agentList.length === 0) {
    return (
      <div className="map-placeholder">
        <div className="map-placeholder-icon">🗺️</div>
        <div>No location data available</div>
        <div style={{ fontSize: '12px', marginTop: '8px' }}>
          Agents without MobilitySpace environment won't have position data
        </div>
      </div>
    );
  }

  const isCartesian = layoutMode !== 'map';

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }} onContextMenu={e => e.preventDefault()}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={layers}
        onHover={(info) => setHovering(Boolean(info.object))}
        getCursor={() => hovering ? 'pointer' : 'grab'}
        onClick={handleClick}
        views={isCartesian ? new OrthographicView({ id: 'ortho', controller: true }) : undefined}
        getTooltip={({ object, layer }) => {
          if (!object || !layer) return null;
          if (layer.id === 'agent-icons' || layer.id === 'agent-circles' || layer.id === 'point' || layer.id === 'text') {
            const agent = agentList.find(a => a.id === object.id);
            if (!agent) return null;
            // Conditional tooltip
            const posText = layoutMode === 'map'
              ? `Position: ${agent.lng.toFixed(4)}, ${agent.lat.toFixed(4)}`
              : (layoutMode === 'network' ? 'Layout: Network' : 'Layout: Random');

            return {
              html: `
                <div style="padding: 8px; font-size: 12px;">
                  <div style="font-weight: bold; margin-bottom: 4px;">${agent.name}</div>
                  <div>ID: ${agent.id}</div>
                  <div>${posText}</div>
                </div>
              `,
              style: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                color: 'white',
                borderRadius: '4px',
              },
            };
          }
          return null;
        }}
      >
        {state.layoutMode === 'map' && (
          <MapGL
            mapboxAccessToken={mapboxToken}
            mapStyle={MAP_STYLE}
            reuseMaps
            style={{ width: '100%', height: '100%' }}
            onError={(event: { error?: { message?: string } }) => {
              const message = event?.error?.message ?? 'Mapbox 加载失败';
              setMapError(message);
            }}
          />
        )}
      </DeckGL>

      {/* Legend */}
      <div style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        padding: '12px',
        background: 'rgba(0, 0, 0, 0.8)',
        borderRadius: '8px',
        fontSize: '11px',
        color: 'white',
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>Agent Positions</div>
        <div>{agentList.length} agents visible</div>
        <div style={{ opacity: 0.7, marginTop: '4px' }}>Zoom: {viewState.zoom.toFixed(1)}</div>
        {selectedAgentId !== null && (
          <div style={{ marginTop: '4px', color: '#ff6384' }}>
            Selected: Agent {selectedAgentId}
          </div>
        )}
      </div>

      {mapError && (
        <div style={{
          position: 'absolute',
          top: 16,
          left: 16,
          padding: '10px 12px',
          background: 'rgba(255, 255, 255, 0.9)',
          borderRadius: '8px',
          fontSize: '12px',
          color: '#b00020',
          maxWidth: '360px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        }}>
          {t('replay.map.loadFailed')}: {mapError}
        </div>
      )}
    </div>
  );
};
