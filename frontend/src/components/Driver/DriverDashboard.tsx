import React, { useState, useEffect } from 'react';
import { RoadEvent, Report, RouteSafetyResponse } from '../../types';
import { fetchRoadEvents, createReport, fetchMyReports, checkRouteSafety } from '../../services/api';
import { wsClient } from '../../services/websocket';
import { InteractiveMap } from '../Map/InteractiveMap';
import { useConfig } from '../../context/ConfigContext';
import {
  AlertTriangle, Navigation, PlusCircle, History, ShieldCheck, X
} from 'lucide-react';

interface DriverDashboardProps {
  onBboxChange?: (bbox: [number, number, number, number]) => void;
}

export const DriverDashboard: React.FC<DriverDashboardProps> = ({ onBboxChange: parentBboxChange }) => {
  const [events, setEvents] = useState<RoadEvent[]>([]);
  const [myReports, setMyReports] = useState<Report[]>([]);
  const [activeTab, setActiveTab] = useState<'map' | 'reports' | 'route'>('map');
  const [proximityAlert, setProximityAlert] = useState<{ event: RoadEvent; distanceM: number } | null>(null);

  // Manual Report Modal State
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportLat, setReportLat] = useState(19.0760);
  const [reportLon, setReportLon] = useState(72.8777);
  const [reportDesc, setReportDesc] = useState('');
  const [submittingReport, setSubmittingReport] = useState(false);

  // Google Maps Directions Search State
  const [originInput, setOriginInput] = useState('Bandra West, Mumbai');
  const [destInput, setDestInput] = useState('Andheri East, Mumbai');
  const [routePolyline, setRoutePolyline] = useState<[number, number][]>([]);
  const [routeSafetyResult, setRouteSafetyResult] = useState<RouteSafetyResponse | null>(null);
  const [checkingRoute, setCheckingRoute] = useState(false);

  const { getSeverityColor, getSeverityLabel, getEventTypeLabel } = useConfig();

  const checkProximityAlert = (newEvent: RoadEvent) => {
    const driverLat = 19.0750;
    const driverLon = 72.8800;
    const latDiff = Math.abs(newEvent.latitude - driverLat);
    const lonDiff = Math.abs(newEvent.longitude - driverLon);

    if (latDiff < 0.02 && lonDiff < 0.02 && newEvent.severity >= 0.6) {
      setProximityAlert({
        event: newEvent,
        distanceM: Math.round(latDiff * 111000),
      });
    }
  };

  useEffect(() => {
    fetchRoadEvents().then(setEvents).catch(console.error);
    fetchMyReports().then(setMyReports).catch(console.error);

    const unsubscribe = wsClient.addListener((type, data) => {
      if (type === 'event_created') {
        const newEvt = data as RoadEvent;
        setEvents((prev) => {
          if (prev.some((e) => e.id === newEvt.id)) {
            return prev.map((e) => (e.id === newEvt.id ? newEvt : e));
          }
          return [newEvt, ...prev];
        });
        checkProximityAlert(newEvt);
      } else if (type === 'event_updated') {
        setEvents((prev) =>
          prev.map((e) => (e.id === data.event_id ? { ...e, status: data.status } : e))
        );
      }
    });

    return () => unsubscribe();
  }, []);

  const handleBboxChange = (bbox: [number, number, number, number]) => {
    wsClient.subscribeBbox(bbox);
    fetchRoadEvents(bbox.join(',')).then(setEvents).catch(console.error);
    // Notify parent (App.tsx) for reconnect reconciliation bbox tracking
    if (parentBboxChange) parentBboxChange(bbox);
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingReport(true);
    try {
      const newReport = await createReport({
        latitude: reportLat,
        longitude: reportLon,
        description: reportDesc,
      });
      setMyReports((prev) => [newReport, ...prev]);
      setShowReportModal(false);
      setReportDesc('');
      alert('Hazard report successfully submitted!');
    } catch (err) {
      alert('Failed to submit report. Please try again.');
    } finally {
      setSubmittingReport(false);
    }
  };

  // Google Maps Directions Route Safety Check
  const handleRunRouteCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    setCheckingRoute(true);

    const fallbackSamplePoly: [number, number][] = [
      [19.0600, 72.8700],
      [19.0728, 72.8826],
      [19.0815, 72.8890],
      [19.0950, 72.8710],
      [19.1100, 72.8500],
    ];

    try {
      const res = await checkRouteSafety(fallbackSamplePoly, originInput, destInput);
      setRouteSafetyResult(res);
      if (res.segment_scores && res.segment_scores.length > 0) {
        const polyPts = res.segment_scores.map((s) => s.start_point);
        polyPts.push(res.segment_scores[res.segment_scores.length - 1].end_point);
        setRoutePolyline(polyPts);
      } else {
        setRoutePolyline(fallbackSamplePoly);
      }
    } catch (err) {
      console.error('Route safety check failed:', err);
      setRoutePolyline(fallbackSamplePoly);
    } finally {
      setCheckingRoute(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', position: 'relative' }}>
      {/* Left Sidebar Drawer */}
      <div
        className="glass-panel"
        style={{
          width: '380px',
          margin: '16px',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          borderRadius: '16px',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Driver Tabs */}
        <div style={{ display: 'flex', background: 'rgba(17, 24, 39, 0.9)', borderBottom: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setActiveTab('map')}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              background: activeTab === 'map' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'map' ? '#818cf8' : 'var(--text-secondary)',
              borderBottom: activeTab === 'map' ? '2px solid #6366f1' : 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <Navigation size={16} />
            Live Map
          </button>
          <button
            onClick={() => setActiveTab('route')}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              background: activeTab === 'route' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'route' ? '#818cf8' : 'var(--text-secondary)',
              borderBottom: activeTab === 'route' ? '2px solid #6366f1' : 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <ShieldCheck size={16} />
            Google Route Risk
          </button>
          <button
            onClick={() => setActiveTab('reports')}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              background: activeTab === 'reports' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
              color: activeTab === 'reports' ? '#818cf8' : 'var(--text-secondary)',
              borderBottom: activeTab === 'reports' ? '2px solid #6366f1' : 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <History size={16} />
            Reports ({myReports.length})
          </button>
        </div>

        {/* Tab Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
          {activeTab === 'map' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <h4 style={{ fontSize: '14px', color: '#ffffff' }}>Nearby Hazards ({events.length})</h4>
                <button
                  onClick={() => setShowReportModal(true)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'var(--accent-primary)',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  <PlusCircle size={14} />
                  Report Hazard
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {events.map((evt) => {
                  const color = getSeverityColor(evt.severity);
                  return (
                    <div key={evt.id} className="glass-panel-interactive" style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: '#ffffff' }}>
                          {getEventTypeLabel(evt.event_type)}
                        </span>
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: `${color}22`,
                            color: color,
                            border: `1px solid ${color}44`,
                          }}
                        >
                          {getSeverityLabel(evt.severity)}
                        </span>
                      </div>
                      <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Confidence: {(evt.confidence * 100).toFixed(0)}% • {evt.corroboration_count} vehicle corroboration(s)
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === 'route' && (
            <div>
              <h4 style={{ fontSize: '14px', marginBottom: '8px' }}>Google Maps Route Safety Checker</h4>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                Annotates driving route polyline using Google Maps Directions API & spatial hazard intelligence.
              </p>

              <form onSubmit={handleRunRouteCheck} style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>Origin Location</label>
                  <input
                    type="text"
                    value={originInput}
                    onChange={(e) => setOriginInput(e.target.value)}
                    placeholder="e.g. Bandra West, Mumbai"
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '12px' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>Destination Location</label>
                  <input
                    type="text"
                    value={destInput}
                    onChange={(e) => setDestInput(e.target.value)}
                    placeholder="e.g. Andheri East, Mumbai"
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '12px' }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={checkingRoute}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: 'pointer',
                    marginTop: '4px',
                  }}
                >
                  {checkingRoute ? 'Querying Google Directions & Safety...' : 'Analyze Google Maps Driving Route'}
                </button>
              </form>

              {routeSafetyResult && (
                <div className="glass-panel" style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Official Road Score:</span>
                    {routeSafetyResult.overall_safety_score !== null ? (
                      <span
                        style={{
                          fontSize: '24px',
                          fontWeight: 800,
                          color: routeSafetyResult.overall_safety_score > 70 ? '#4ade80' : '#f87171',
                        }}
                      >
                        {routeSafetyResult.overall_safety_score} / 100
                      </span>
                    ) : (
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#f59e0b' }}>
                        No scored road-network data
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    <div>Hazards on Route: <b style={{ color: '#ef4444' }}>{routeSafetyResult.detected_hazards_on_route.length}</b></div>
                    <div>Scored Segments: <b>{routeSafetyResult.scored_segments_count}</b></div>
                    <div>Unscored Stretches: <b>{routeSafetyResult.unscored_stretches_count}</b></div>
                  </div>

                  <div style={{ fontSize: '10px', padding: '6px 8px', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                    📍 Hazard Location Intelligence Stretch (Unscored Network)
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'reports' && (
            <div>
              <h4 style={{ fontSize: '14px', marginBottom: '12px' }}>My Submitted Hazard Reports</h4>
              {myReports.length === 0 ? (
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No manual reports submitted yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {myReports.map((rpt) => (
                    <div key={rpt.id} className="glass-panel" style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600, color: '#f3f4f6' }}>{rpt.description || 'Hazard Report'}</span>
                        <span style={{ fontSize: '10px', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase' }}>{rpt.status}</span>
                      </div>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                        GPS: {rpt.latitude.toFixed(4)}, {rpt.longitude.toFixed(4)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main Map View */}
      <div style={{ flex: 1, padding: '16px 16px 16px 0', position: 'relative' }}>
        <InteractiveMap events={events} onBboxChange={handleBboxChange} routePolyline={routePolyline} />

        {/* Proximity Hazard Alert Banner */}
        {proximityAlert && (
          <div
            className="glass-panel badge-severity-critical"
            style={{
              position: 'absolute',
              top: '32px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 1000,
              padding: '12px 20px',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              boxShadow: '0 10px 40px rgba(239, 68, 68, 0.4)',
            }}
          >
            <AlertTriangle size={24} color="#f87171" />
            <div>
              <h4 style={{ fontSize: '14px', color: '#ffffff' }}>PROXIMITY WARNING — {getEventTypeLabel(proximityAlert.event.event_type).toUpperCase()}</h4>
              <p style={{ fontSize: '12px', color: '#fca5a5' }}>
                High-severity hazard detected {proximityAlert.distanceM}m ahead. Slow down.
              </p>
            </div>
            <button
              onClick={() => setProximityAlert(null)}
              style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer' }}
            >
              <X size={18} />
            </button>
          </div>
        )}
      </div>

      {/* Report Hazard Modal */}
      {showReportModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
          <div className="glass-panel" style={{ width: '420px', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '12px' }}>Report Road Hazard</h3>
            <form onSubmit={handleReportSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Description</label>
                <textarea
                  value={reportDesc}
                  onChange={(e) => setReportDesc(e.target.value)}
                  placeholder="e.g. Deep pothole causing tire damage near junction..."
                  rows={3}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '13px' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={reportLat}
                    onChange={(e) => setReportLat(parseFloat(e.target.value))}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '12px' }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={reportLon}
                    onChange={(e) => setReportLon(parseFloat(e.target.value))}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '12px' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowReportModal(false)}
                  style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'transparent', color: '#9ca3af', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReport}
                  style={{ padding: '8px 20px', borderRadius: '6px', border: 'none', background: 'var(--accent-primary)', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
                >
                  {submittingReport ? 'Submitting...' : 'Submit Report'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
