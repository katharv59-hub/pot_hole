import React, { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import type { Feature, LineString } from 'geojson';
import { RoadEvent } from '../../types';
import { useConfig } from '../../context/ConfigContext';
import { Key } from 'lucide-react';

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
  const [tokenMissing, setTokenMissing] = useState<boolean>(false);

  const { getSeverityColor, getSeverityLabel, getEventTypeLabel } = useConfig();

  // Retrieve token from Vite environment
  const mapboxToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || '';

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
      setTokenMissing(true);
      return;
    }

    setTokenMissing(false);
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
      el.style.width = isSelected ? '32px' : '24px';
      el.style.height = isSelected ? '32px' : '24px';
      el.style.borderRadius = '50%';
      el.style.backgroundColor = color;
      el.style.border = '2px solid #ffffff';
      el.style.boxShadow = `0 0 15px ${color}`;
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.color = '#ffffff';
      el.style.fontWeight = 'bold';
      el.style.fontSize = '11px';
      el.style.cursor = 'pointer';

      if (isCritical) {
        el.style.animation = 'pulse-critical 2s infinite';
      }

      if (evt.corroboration_count > 1) {
        el.innerText = String(evt.corroboration_count);
      }

      // Create Popup HTML
      const popupHtml = `
        <div style="padding: 4px; min-width: 220px; font-family: 'Inter', sans-serif;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-weight: 700; font-size: 14px; color: #ffffff;">${getEventTypeLabel(evt.event_type)}</span>
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
          
          <div style="font-size: 11px; color: #9ca3af; margin-bottom: 8px; line-height: 1.5;">
            <div>Status: <b style="color: #f3f4f6;">${evt.status.toUpperCase()}</b></div>
            <div>Confidence: <b style="color: #818cf8;">${(evt.confidence * 100).toFixed(0)}%</b></div>
            <div>Corroborated: <b style="color: #4ade80;">${evt.corroboration_count} vehicle(s)</b></div>
            <div>Modality: <b style="color: #c084fc;">${(evt.modality_sources || []).join(', ')}</b></div>
          </div>

          <div style="
            font-size: 10px;
            padding: 4px 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.05);
            color: #9ca3af;
            border: 1px dashed rgba(255,255,255,0.15);
          ">
            🗺️ Lat: ${evt.latitude.toFixed(4)}, Lon: ${evt.longitude.toFixed(4)}
          </div>
        </div>
      `;

      const popup = new mapboxgl.Popup({
        offset: 25,
        closeButton: true,
        closeOnClick: false,
        maxWidth: '300px',
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
          borderRadius: '12px',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0b0f19',
          border: '1px dashed rgba(239, 68, 68, 0.4)',
        }}
      >
        <div
          className="glass-panel"
          style={{
            padding: '24px 32px',
            maxWidth: '480px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ef4444',
            }}
          >
            <Key size={24} />
          </div>
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f9fafb' }}>
            Mapbox GL Access Token Required
          </h3>
          <p style={{ fontSize: '13px', color: '#9ca3af', lineHeight: 1.5 }}>
            To render the ROADSentinel v0.4 spatial map, please configure{' '}
            <code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px', color: '#a5b4fc' }}>
              VITE_MAPBOX_ACCESS_TOKEN
            </code>{' '}
            in your <code style={{ color: '#a5b4fc' }}>frontend/.env</code> file.
          </p>
          <div
            style={{
              fontSize: '11px',
              color: '#6b7280',
              marginTop: '4px',
              borderTop: '1px solid rgba(255,255,255,0.1)',
              paddingTop: '8px',
              width: '100%',
            }}
          >
            Engine: Mapbox GL JS (v0.4 Specification Compliance)
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: '12px', overflow: 'hidden' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* Mapbox Style Switcher Control */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          top: '20px',
          right: '20px',
          zIndex: 10,
          padding: '6px',
          borderRadius: '10px',
          display: 'flex',
          gap: '4px',
        }}
      >
        <button
          onClick={() => setMapStyle('dark')}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            background: mapStyle === 'dark' ? '#6366f1' : 'transparent',
            color: mapStyle === 'dark' ? '#fff' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '11px',
            cursor: 'pointer',
          }}
        >
          Dark
        </button>
        <button
          onClick={() => setMapStyle('satellite')}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            background: mapStyle === 'satellite' ? '#6366f1' : 'transparent',
            color: mapStyle === 'satellite' ? '#fff' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '11px',
            cursor: 'pointer',
          }}
        >
          Satellite
        </button>
        <button
          onClick={() => setMapStyle('navigation')}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            background: mapStyle === 'navigation' ? '#6366f1' : 'transparent',
            color: mapStyle === 'navigation' ? '#fff' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '11px',
            cursor: 'pointer',
          }}
        >
          Navigation
        </button>
        <button
          onClick={() => setMapStyle('streets')}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            background: mapStyle === 'streets' ? '#6366f1' : 'transparent',
            color: mapStyle === 'streets' ? '#fff' : 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '11px',
            cursor: 'pointer',
          }}
        >
          Streets
        </button>
      </div>

      {/* Floating Severity Legend */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          bottom: '20px',
          left: '20px',
          zIndex: 10,
          padding: '12px 16px',
          borderRadius: '10px',
          display: 'flex',
          gap: '16px',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Severity:
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22c55e' }}></span> Low
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#eab308' }}></span> Medium
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f97316' }}></span> High
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }}></span> Critical
        </div>
      </div>
    </div>
  );
};
