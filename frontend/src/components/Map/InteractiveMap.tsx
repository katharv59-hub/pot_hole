import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { RoadEvent } from '../../types';
import { useConfig } from '../../context/ConfigContext';
import { ShieldAlert, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface InteractiveMapProps {
  events: RoadEvent[];
  selectedEventId?: string | null;
  onSelectEvent?: (event: RoadEvent) => void;
  onBboxChange?: (bbox: [number, number, number, number]) => void;
  routePolyline?: [number, number][];
  center?: [number, number];
  zoom?: number;
}

export const InteractiveMap: React.FC<InteractiveMapProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  onBboxChange,
  routePolyline,
  center = [19.0760, 72.8777], // Default to Mumbai Metropolitan region
  zoom = 13,
}) => {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const polylineLayerRef = useRef<L.Polyline | null>(null);

  const { getSeverityColor, getSeverityLabel, getEventTypeLabel } = useConfig();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Initialize Leaflet Map
    const map = L.map(containerRef.current, {
      center: center,
      zoom: zoom,
      zoomControl: false,
    });

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Dark Map Tile Layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    // Listen to Map Move / Zoom events and emit bounding box [minLon, minLat, maxLon, maxLat]
    const emitBbox = () => {
      if (!map || !onBboxChange) return;
      const bounds = map.getBounds();
      const bbox: [number, number, number, number] = [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ];
      onBboxChange(bbox);
    };

    map.on('moveend', emitBbox);
    map.on('zoomend', emitBbox);
    emitBbox(); // Initial emission

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update Hazard Markers on Map
  useEffect(() => {
    const map = mapRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    events.forEach((evt) => {
      const color = getSeverityColor(evt.severity);
      const isSelected = selectedEventId === evt.id;
      const isCritical = evt.severity >= 0.8;

      // Custom HTML Marker Element
      const customIcon = L.divIcon({
        className: 'custom-hazard-icon',
        html: `
          <div style="
            width: ${isSelected ? '32px' : '24px'};
            height: ${isSelected ? '32px' : '24px'};
            border-radius: 50%;
            background: ${color};
            border: 2px solid #ffffff;
            box-shadow: 0 0 15px ${color};
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: bold;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
            ${isCritical ? 'animation: pulse-critical 2s infinite;' : ''}
          ">
            ${evt.corroboration_count > 1 ? evt.corroboration_count : ''}
          </div>
        `,
        iconSize: [isSelected ? 32 : 24, isSelected ? 32 : 24],
        iconAnchor: [isSelected ? 16 : 12, isSelected ? 16 : 12],
      });

      const marker = L.marker([evt.latitude, evt.longitude], { icon: customIcon });

      // Interactive Popup Content
      const popupHtml = `
        <div style="padding: 8px; min-width: 200px;">
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
          
          <div style="font-size: 11px; color: #9ca3af; margin-bottom: 8px;">
            <div>Status: <b style="color: #f3f4f6;">${evt.status.toUpperCase()}</b></div>
            <div>Confidence: <b style="color: #818cf8;">${(evt.confidence * 100).toFixed(0)}%</b></div>
            <div>Independent Devices: <b style="color: #4ade80;">${evt.corroboration_count} vehicle(s)</b></div>
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
            📍 Framing: Location Intelligence (Unscored Segment)
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on('click', () => {
        if (onSelectEvent) onSelectEvent(evt);
      });

      markersLayer.addLayer(marker);
    });
  }, [events, selectedEventId]);

  // Update Route Polyline Layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (polylineLayerRef.current) {
      map.removeLayer(polylineLayerRef.current);
      polylineLayerRef.current = null;
    }

    if (routePolyline && routePolyline.length > 1) {
      const latLngs: L.LatLngExpression[] = routePolyline.map((pt) => [pt[0], pt[1]]);
      const polyline = L.polyline(latLngs, {
        color: '#6366f1',
        weight: 6,
        opacity: 0.85,
        dashArray: '10, 10',
      }).addTo(map);

      polylineLayerRef.current = polyline;
      map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
    }
  }, [routePolyline]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: '12px', overflow: 'hidden' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Map Floating Legend */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          bottom: '20px',
          left: '20px',
          zIndex: 1000,
          padding: '12px 16px',
          borderRadius: '10px',
          display: 'flex',
          gap: '16px',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Severity Legend:
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
