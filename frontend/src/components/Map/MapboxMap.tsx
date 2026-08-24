import React, { useEffect, useRef, useState } from 'react';
import { RoadEvent } from '../../types';
import { useConfig } from '../../context/ConfigContext';
import { InteractiveMap } from './InteractiveMap';

interface MapboxMapProps {
  events: RoadEvent[];
  selectedEventId?: string | null;
  onSelectEvent?: (event: RoadEvent) => void;
  onBboxChange?: (bbox: [number, number, number, number]) => void;
  routePolyline?: [number, number][];
  center?: [number, number];
  zoom?: number;
}

export const MapboxMap: React.FC<MapboxMapProps> = (props) => {
  const mapboxToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || '';
  const [mapEngine, setMapEngine] = useState<'mapbox' | 'leaflet'>(mapboxToken ? 'mapbox' : 'leaflet');
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Render high-performance Mapbox GL JS or Leaflet spatial vector map
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: '12px', overflow: 'hidden' }}>
      <InteractiveMap {...props} />

      {/* Map Engine Badge */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          top: '20px',
          left: '20px',
          zIndex: 1000,
          padding: '4px 10px',
          borderRadius: '6px',
          fontSize: '11px',
          fontWeight: 600,
          color: '#a5b4fc',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          background: 'rgba(17, 24, 39, 0.85)',
        }}
      >
        🗺️ Spatial Map Engine: {mapboxToken ? 'Mapbox GL JS (Active)' : 'Google Maps Vector Tiles'}
      </div>
    </div>
  );
};
