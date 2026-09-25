import React, { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import type { Feature, LineString } from 'geojson';
import { RoadEvent } from '../../types';
import { useConfig } from '../../context/ConfigContext';
import { Key } from 'lucide-react';
import { Button, Panel } from '../ui';

interface InteractiveMapProps {
  events: RoadEvent[];
  selectedEventId?: string | null;
  onSelectEvent?: (event: RoadEvent) => void;
  onBboxChange?: (bbox: [number, number, number, number]) => void;
  routePolyline?: [number, number][];
  center?: [number, number]; // [latitude, longitude] or [longitude, latitude]
  zoom?: number;
}

const MAPBOX_STYLES = {
  dark: 'mapbox://styles/mapbox/dark-v11',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  navigation: 'mapbox://styles/mapbox/navigation-night-v1',
  streets: 'mapbox://styles/mapbox/streets-v12',
};

type StyleKey = keyof typeof MAPBOX_STYLES;

export const InteractiveMap: React.FC<InteractiveMapProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  onBboxChange,
  routePolyline,
  center = [19.0760, 72.8777], // Mumbai Metropolitan region [lat, lon]
  zoom = 13,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const isLoadedRef = useRef<boolean>(false);

  const [mapStyle, setMapStyle] = useState<StyleKey>('dark');
  const { getSeverityColor, getSeverityLabel, getEventTypeLabel } = useConfig();

  const mapboxToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || '';
  const tokenMissing = !mapboxToken;

  // Convert incoming [lat, lon] center to Mapbox [lng, lat]
  const mapboxCenter: [number, number] =
    center[0] > 60 && center[1] < 40
      ? [center[0], center[1]] // already [lng, lat]
      : [center[1], center[0]]; // was [lat, lon]

  // Calculate and emit bounding box [west, south, east, north]
  const emitBbox = useCallback(() => {
    const map = mapRef.current;
    if (!map || !onBboxChange) return;

    const bounds = map.getBounds();
    if (!bounds) return;

    const bbox: [number, number, number, number] = [
      bounds.getWest(),
      bounds.getSouth(),
      bounds.getEast(),
      bounds.getNorth(),
    ];
    onBboxChange(bbox);
  }, [onBboxChange]);

  // Helper to add or update route polyline layer
  const updateRouteLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map || !isLoadedRef.current) return;

    // Convert [lat, lon] array to Mapbox [lng, lat] array
    const coordinates: [number, number][] = (routePolyline || []).map((pt) => [pt[1], pt[0]]);

    const geojsonData: Feature<LineString> = {
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'LineString',
        coordinates: coordinates.length > 1 ? coordinates : [],
      },
    };

    const source = map.getSource('route-source') as mapboxgl.GeoJSONSource | undefined;
    if (source) {
      source.setData(geojsonData);
    } else if (coordinates.length > 1) {
      map.addSource('route-source', {
        type: 'geojson',
        data: geojsonData,
      });

      map.addLayer({
        id: 'route-layer',
        type: 'line',
        source: 'route-source',
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
        },
        paint: {
          'line-color': '#6366f1',
          'line-width': 5,
          'line-opacity': 0.85,
        },
      });
    }

    if (coordinates.length > 1) {
      const bounds = new mapboxgl.LngLatBounds();
      coordinates.forEach((coord) => bounds.extend(coord));
      map.fitBounds(bounds, { padding: 60, maxZoom: 16 });
    }
  }, [routePolyline]);

  // Initialize Mapbox Map Instance
  useEffect(() => {
    if (!mapboxToken) {
      return;
    }

    mapboxgl.accessToken = mapboxToken;

    if (!mapContainerRef.current || mapRef.current) return;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: MAPBOX_STYLES[mapStyle],
      center: mapboxCenter,
      zoom: zoom,
      attributionControl: false,
    });

    // Add navigation controls (zoom & compass)
    map.addControl(new mapboxgl.NavigationControl({ showCompass: true }), 'bottom-right');
    map.addControl(new mapboxgl.AttributionControl({ compact: true }), 'bottom-left');

    map.on('load', () => {
      isLoadedRef.current = true;
      emitBbox();
      updateRouteLayer();
    });

    map.on('moveend', emitBbox);
    map.on('zoomend', emitBbox);

    mapRef.current = map;

    return () => {
      isLoadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, [mapboxToken]);

  // Handle Style Switching
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const targetStyle = MAPBOX_STYLES[mapStyle];
    map.setStyle(targetStyle);

    map.once('style.load', () => {
      updateRouteLayer();
    });
  }, [mapStyle, updateRouteLayer]);

  // Handle Route Polyline Updates
  useEffect(() => {
    updateRouteLayer();
  }, [routePolyline, updateRouteLayer]);

  // Render & Update Event Markers on Map
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear existing markers
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    events.forEach((evt) => {
      const color = getSeverityColor(evt.severity);
      const isSelected = selectedEventId === evt.id;
      const isCritical = evt.severity >= 0.8;

      // Create Custom Marker DOM Element
      const el = document.createElement('div');
      el.className = 'custom-mapbox-marker';
      el.style.width = isSelected ? '30px' : '22px';
      el.style.height = isSelected ? '30px' : '22px';
      el.style.borderRadius = '50%';
      el.style.backgroundColor = color;
      el.style.border = isSelected ? '3px solid #ffffff' : '2px solid rgba(255, 255, 255, 0.9)';
      el.style.boxShadow = isSelected ? `0 0 18px ${color}` : `0 0 10px ${color}88`;
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.color = '#ffffff';
      el.style.fontWeight = '700';
      el.style.fontSize = '10px';
      el.style.cursor = 'pointer';

      if (isCritical) {
        const pulseRing = document.createElement('div');
        pulseRing.className = 'critical-pulse-ring';
        el.appendChild(pulseRing);
      }

      if (evt.corroboration_count > 1) {
        const span = document.createElement('span');
        span.innerText = String(evt.corroboration_count);
        el.appendChild(span);
      }

      // Create Popup HTML
      const popupHtml = `
        <div style="padding: 2px; min-width: 210px; font-family: 'Inter', sans-serif;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 13px; color: var(--text-primary); font-family: 'Outfit', sans-serif;">${getEventTypeLabel(evt.event_type)}</span>
            <span style="
              font-size: 10px;
              font-weight: 700;
              padding: 2px 6px;
              border-radius: 4px;
              background: ${color}22;
              color: ${color};
              border: 1px solid ${color}66;
            ">${getSeverityLabel(evt.severity).toUpperCase()} (${(evt.severity * 100).toFixed(0)}%)</span>
          </div>
          
          <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.6;">
            <div>Status: <b style="color: var(--text-primary); font-variant-numeric: tabular-nums;">${evt.status.toUpperCase()}</b></div>
            <div>Confidence: <b style="color: var(--accent-cyan); font-variant-numeric: tabular-nums;">${(evt.confidence * 100).toFixed(0)}%</b></div>
            <div>Corroborated: <b style="color: var(--severity-low); font-variant-numeric: tabular-nums;">${evt.corroboration_count} vehicle(s)</b></div>
            <div>Sources: <b style="color: var(--text-primary);">${(evt.modality_sources || []).join(', ')}</b></div>
          </div>

          <div style="
            font-size: 10px;
            font-family: 'JetBrains Mono', monospace;
            padding: 4px 6px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-tertiary);
            border: 1px solid var(--border-subtle);
          ">
            LOC: ${evt.latitude.toFixed(5)}, ${evt.longitude.toFixed(5)}
          </div>
        </div>
      `;

      const popup = new mapboxgl.Popup({
        offset: 22,
        closeButton: true,
        closeOnClick: false,
        maxWidth: '320px',
      }).setHTML(popupHtml);

      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([evt.longitude, evt.latitude])
        .setPopup(popup)
        .addTo(map);

      el.addEventListener('click', () => {
        if (onSelectEvent) {
          onSelectEvent(evt);
        }
      });

      markersRef.current.push(marker);
    });
  }, [events, selectedEventId, getSeverityColor, getSeverityLabel, getEventTypeLabel, onSelectEvent]);

  // Render Token Missing Error State
  if (tokenMissing) {
    return (
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--surface-app)',
          border: '1px dashed rgba(239, 68, 68, 0.4)',
        }}
      >
        <Panel
          level="card"
          style={{
            padding: 'var(--space-6) var(--space-8)',
            maxWidth: '480px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'var(--space-3)',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--severity-critical)',
            }}
          >
            <Key size={22} />
          </div>
          <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Mapbox GL Access Token Required
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            To render the ROADSentinel spatial map, configure{' '}
            <code style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: '4px', color: 'var(--accent-cyan)' }}>
              VITE_MAPBOX_ACCESS_TOKEN
            </code>{' '}
            in your <code style={{ color: 'var(--accent-cyan)' }}>frontend/.env</code> file.
          </p>
        </Panel>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Mapbox Style Switcher Control */}
      <Panel
        level="hud"
        padded={false}
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          zIndex: 10,
          padding: '3px',
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          gap: '2px',
        }}
      >
        {(['dark', 'satellite', 'navigation', 'streets'] as StyleKey[]).map((style) => (
          <Button
            key={style}
            variant={mapStyle === style ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setMapStyle(style)}
            style={{
              height: '26px',
              fontSize: '11px',
              padding: '0 10px',
              textTransform: 'capitalize',
            }}
          >
            {style}
          </Button>
        ))}
      </Panel>

      {/* Floating Severity Legend */}
      <Panel
        level="hud"
        padded={false}
        style={{
          position: 'absolute',
          bottom: '20px',
          left: '20px',
          zIndex: 10,
          padding: '8px 14px',
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Severity:
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-secondary)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--severity-low)' }} /> Low
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-secondary)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--severity-medium)' }} /> Medium
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-secondary)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--severity-high)' }} /> High
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-secondary)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--severity-critical)' }} /> Critical
        </div>
      </Panel>
    </div>
  );
};
