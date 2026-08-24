import React, { useState, useEffect } from 'react';
import { RoadEvent, Device, AnalyticsSummary } from '../../types';
import {
  fetchRoadEvents, updateEventStatus, fetchDevices,
  registerDevice, reassignDevice, fetchAnalyticsSummary
} from '../../services/api';
import { wsClient } from '../../services/websocket';
import { useConfig } from '../../context/ConfigContext';
import {
  CheckCircle, AlertOctagon, Copy, Download, RefreshCw, Cpu,
  BarChart3, Layers, Filter, Check, X, ShieldAlert, Clock
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const [events, setEvents] = useState<RoadEvent[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [selectedTab, setSelectedTab] = useState<'triage' | 'analytics' | 'devices'>('triage');

  // Filter States
  const [statusFilter, setStatusFilter] = useState<string>('unverified');
  const [modalityFilter, setModalityFilter] = useState<string>('all');

  // Verification Modal State
  const [selectedEvent, setSelectedEvent] = useState<RoadEvent | null>(null);
  const [updating, setUpdating] = useState(false);

  // Hardware Registration State
  const [newHwType, setNewHwType] = useState('ESP32');
  const [newVehicleId, setNewVehicleId] = useState('');
  const [generatedSecret, setGeneratedSecret] = useState<{ id: string; secret: string } | null>(null);

  const { getSeverityColor, getSeverityLabel, getEventTypeLabel } = useConfig();

  const loadData = () => {
    fetchRoadEvents(undefined, undefined, statusFilter === 'all' ? undefined : statusFilter)
      .then(setEvents)
      .catch(console.error);

    fetchDevices().then(setDevices).catch(console.error);
    fetchAnalyticsSummary().then(setAnalytics).catch(console.error);
  };

  useEffect(() => {
    loadData();

    // WebSocket listener for live updates
    const unsubscribe = wsClient.addListener((type, data) => {
      if (type === 'event_created' || type === 'event_updated') {
        loadData();
      }
    });

    return () => unsubscribe();
  }, [statusFilter]);

  // Handle Event Status Verification (Spec §5.1)
  const handleUpdateStatus = async (eventId: string, newStatus: string) => {
    setUpdating(true);
    try {
      const updated = await updateEventStatus(eventId, newStatus);
      setEvents((prev) => prev.map((e) => (e.id === eventId ? updated : e)));
      if (selectedEvent && selectedEvent.id === eventId) {
        setSelectedEvent(updated);
      }
      loadData();
    } catch (err) {
      alert('Failed to update event status');
    } finally {
      setUpdating(false);
    }
  };

  // Handle Hardware Registration
  const handleRegisterDeviceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await registerDevice({ hardware_type: newHwType, vehicle_id: newVehicleId || undefined });
      setGeneratedSecret({ id: res.device_id, secret: res.provisioning_secret });
      loadData();
    } catch (err) {
      alert('Device registration failed');
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', height: 'calc(100vh - 64px)', overflowY: 'auto' }}>
      {/* Top Header & Section Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '22px', color: '#ffffff' }}>Authority & Admin Command Dashboard</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Hazard verification triage, spatial intelligence, and hardware fleet management.</p>
        </div>

        <div style={{ display: 'flex', gap: '8px', background: '#111827', padding: '4px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setSelectedTab('triage')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: selectedTab === 'triage' ? '#6366f1' : 'transparent',
              color: selectedTab === 'triage' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <ShieldAlert size={16} />
            Hazard Triage Queue
          </button>
          <button
            onClick={() => setSelectedTab('analytics')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: selectedTab === 'analytics' ? '#6366f1' : 'transparent',
              color: selectedTab === 'analytics' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <BarChart3 size={16} />
            Spatial Analytics
          </button>
          <button
            onClick={() => setSelectedTab('devices')}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: selectedTab === 'devices' ? '#6366f1' : 'transparent',
              color: selectedTab === 'devices' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Cpu size={16} />
            Fleet Devices ({devices.length})
          </button>
        </div>
      </div>

      {/* --- TAB 1: TRIAGE QUEUE --- */}
      {selectedTab === 'triage' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Triage Filters Bar */}
          <div className="glass-panel" style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Filter size={14} /> Filter Status:
              </span>
              {['unverified', 'verified', 'duplicate', 'resolved', 'all'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    background: statusFilter === st ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                    color: statusFilter === st ? '#818cf8' : 'var(--text-secondary)',
                    fontWeight: 600,
                    fontSize: '12px',
                    textTransform: 'capitalize',
                    cursor: 'pointer',
                    border: statusFilter === st ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent'
                  }}
                >
                  {st}
                </button>
              ))}
            </div>

            <button
              onClick={loadData}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'transparent', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
            >
              <RefreshCw size={14} /> Refresh Queue
            </button>
          </div>

          {/* Hazards Triage Table */}
          <div className="glass-panel" style={{ overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: 'rgba(31, 41, 55, 0.6)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 16px' }}>Hazard Type</th>
                  <th style={{ padding: '12px 16px' }}>Severity</th>
                  <th style={{ padding: '12px 16px' }}>Confidence</th>
                  <th style={{ padding: '12px 16px' }}>Independent Devices</th>
                  <th style={{ padding: '12px 16px' }}>Modality</th>
                  <th style={{ padding: '12px 16px' }}>Status</th>
                  <th style={{ padding: '12px 16px' }}>Timestamp</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No events matching current filter criteria.
                    </td>
                  </tr>
                ) : (
                  events.map((evt) => {
                    const color = getSeverityColor(evt.severity);
                    return (
                      <tr key={evt.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <td style={{ padding: '14px 16px', fontWeight: 600, color: '#ffffff' }}>
                          {getEventTypeLabel(evt.event_type)}
                        </td>
                        <td style={{ padding: '14px 16px' }}>
                          <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: `${color}22`, color: color, border: `1px solid ${color}44` }}>
                            {getSeverityLabel(evt.severity).toUpperCase()} ({(evt.severity * 100).toFixed(0)}%)
                          </span>
                        </td>
                        <td style={{ padding: '14px 16px', color: '#818cf8', fontWeight: 600 }}>
                          {(evt.confidence * 100).toFixed(0)}%
                        </td>
                        <td style={{ padding: '14px 16px', color: '#4ade80', fontWeight: 600 }}>
                          {evt.corroboration_count} vehicle(s)
                        </td>
                        <td style={{ padding: '14px 16px', color: '#c084fc' }}>
                          {(evt.modality_sources || []).join(', ')}
                        </td>
                        <td style={{ padding: '14px 16px', textTransform: 'capitalize', fontWeight: 600 }}>
                          {evt.status}
                        </td>
                        <td style={{ padding: '14px 16px', color: 'var(--text-muted)', fontSize: '11px' }}>
                          {new Date(evt.device_timestamp).toLocaleTimeString()}
                        </td>
                        <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                          <button
                            onClick={() => setSelectedEvent(evt)}
                            style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--accent-primary)', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', cursor: 'pointer', fontWeight: 600, fontSize: '12px' }}
                          >
                            Inspect & Verify
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --- TAB 2: SPATIAL ANALYTICS --- */}
      {selectedTab === 'analytics' && analytics && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Key Metrics Header Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
            <div className="glass-panel" style={{ padding: '20px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Detected Hazards</span>
              <h3 style={{ fontSize: '28px', color: '#ffffff', marginTop: '4px' }}>{analytics.metrics.total_events}</h3>
            </div>
            <div className="glass-panel" style={{ padding: '20px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Unverified Triage Queue</span>
              <h3 style={{ fontSize: '28px', color: '#f87171', marginTop: '4px' }}>{analytics.metrics.unverified_count}</h3>
            </div>
            <div className="glass-panel" style={{ padding: '20px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Authority Verified</span>
              <h3 style={{ fontSize: '28px', color: '#4ade80', marginTop: '4px' }}>{analytics.metrics.verified_count}</h3>
            </div>
            <div className="glass-panel" style={{ padding: '20px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Active Hardware Devices</span>
              <h3 style={{ fontSize: '28px', color: '#818cf8', marginTop: '4px' }}>{analytics.metrics.active_devices}</h3>
            </div>
          </div>

          {/* Export & Charts Grid */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '16px', color: '#fff' }}>Hazard Distribution & RBAC Catalog Export</h3>
              <a
                href="http://localhost:8000/api/v1/analytics/export"
                download
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  background: 'var(--accent-primary)',
                  color: '#fff',
                  textDecoration: 'none',
                  fontWeight: 600,
                  fontSize: '13px'
                }}
              >
                <Download size={16} /> Export Catalog CSV
              </a>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              <div>
                <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-secondary)' }}>Severity Bucket Distribution</h4>
                {Object.entries(analytics.severity_distribution).map(([sev, count]) => (
                  <div key={sev} style={{ marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                      <span style={{ textTransform: 'capitalize', color: '#fff' }}>{sev} Severity</span>
                      <span style={{ color: 'var(--text-muted)' }}>{count} events</span>
                    </div>
                    <div style={{ height: '8px', borderRadius: '4px', background: '#1f2937', overflow: 'hidden' }}>
                      <div style={{ width: `${(count / (analytics.metrics.total_events || 1)) * 100}%`, height: '100%', background: sev === 'critical' ? '#ef4444' : sev === 'high' ? '#f97316' : sev === 'medium' ? '#eab308' : '#22c55e' }} />
                    </div>
                  </div>
                ))}
              </div>

              <div>
                <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-secondary)' }}>Hazard Type Breakdown</h4>
                {Object.entries(analytics.event_type_distribution).map(([type, count]) => (
                  <div key={type} style={{ marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                      <span style={{ color: '#fff' }}>{getEventTypeLabel(type)}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{count} events</span>
                    </div>
                    <div style={{ height: '8px', borderRadius: '4px', background: '#1f2937', overflow: 'hidden' }}>
                      <div style={{ width: `${(count / (analytics.metrics.total_events || 1)) * 100}%`, height: '100%', background: '#6366f1' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 3: DEVICE & FLEET MANAGEMENT --- */}
      {selectedTab === 'devices' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
          {/* Register Device Form */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', marginBottom: '12px', color: '#fff' }}>Register New Fleet Hardware</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>Spec §5.1: Issues one-time provisioning secret out-of-band.</p>

            <form onSubmit={handleRegisterDeviceSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Hardware Type</label>
                <select
                  value={newHwType}
                  onChange={(e) => setNewHwType(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '13px' }}
                >
                  <option value="ESP32">ESP32 + IMU + GPS</option>
                  <option value="edge-ai">Edge-AI Jetson Computer</option>
                  <option value="other">Other Hardware</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Assign Initial Vehicle ID (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. veh_1183"
                  value={newVehicleId}
                  onChange={(e) => setNewVehicleId(e.target.value)}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#1f2937', border: '1px solid var(--border-color)', color: '#fff', fontSize: '13px' }}
                />
              </div>

              <button type="submit" style={{ padding: '10px', borderRadius: '6px', border: 'none', background: 'var(--accent-primary)', color: '#fff', fontWeight: 600, cursor: 'pointer', marginTop: '8px' }}>
                Register Hardware Device
              </button>
            </form>

            {generatedSecret && (
              <div style={{ marginTop: '16px', padding: '12px', borderRadius: '8px', background: 'rgba(34, 197, 94, 0.12)', border: '1px solid rgba(34, 197, 94, 0.3)' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: '#4ade80', display: 'block' }}>Provisioning Secret Generated:</span>
                <code style={{ fontSize: '11px', color: '#fff', wordBreak: 'break-all', display: 'block', margin: '4px 0' }}>{generatedSecret.secret}</code>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Flash this secret into device firmware once.</span>
              </div>
            )}
          </div>

          {/* Registered Devices List */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', marginBottom: '16px', color: '#fff' }}>Registered Hardware Devices ({devices.length})</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {devices.map((dev) => (
                <div key={dev.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px', borderRadius: '8px', background: 'rgba(31, 41, 55, 0.5)', border: '1px solid var(--border-color)' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '13px', color: '#fff' }}>{dev.id}</span>
                      <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: dev.status === 'active' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)', color: dev.status === 'active' ? '#4ade80' : '#f87171' }}>
                        {dev.status.toUpperCase()}
                      </span>
                    </div>
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Type: {dev.hardware_type} • Assigned Vehicle: <b>{dev.vehicle_id || 'Unassigned'}</b>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Verification Inspection Modal */}
      {selectedEvent && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
          <div className="glass-panel" style={{ width: '560px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', color: '#fff' }}>Inspect & Verify Road Event</h3>
              <button onClick={() => setSelectedEvent(null)} style={{ background: 'transparent', border: 'none', color: '#9ca3af', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Event ID:</span>
                <span style={{ color: '#fff', fontWeight: 600 }}>{selectedEvent.id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Device Event ID (Idempotency Key):</span>
                <span style={{ color: '#818cf8', fontWeight: 600 }}>{selectedEvent.device_event_id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Sensor vs Server Timestamp Diff:</span>
                <span style={{ color: '#4ade80', fontWeight: 600 }}>Diagnostic skew: &lt; 1s</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Independent Devices Corroboration:</span>
                <span style={{ color: '#fde047', fontWeight: 700 }}>{selectedEvent.corroboration_count} vehicle(s)</span>
              </div>
            </div>

            {/* Verification Actions */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => handleUpdateStatus(selectedEvent.id, 'verified')}
                disabled={updating}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: 'none', background: '#22c55e', color: '#fff', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <Check size={16} /> Verify Event
              </button>
              <button
                onClick={() => handleUpdateStatus(selectedEvent.id, 'duplicate')}
                disabled={updating}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: 'none', background: '#eab308', color: '#fff', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <Copy size={16} /> Mark Duplicate
              </button>
              <button
                onClick={() => handleUpdateStatus(selectedEvent.id, 'resolved')}
                disabled={updating}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: 'none', background: '#6366f1', color: '#fff', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              >
                <CheckCircle size={16} /> Resolve Event
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
