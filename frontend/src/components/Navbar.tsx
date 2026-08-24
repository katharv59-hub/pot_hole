import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, Navigation, Activity, Wifi, WifiOff, LogOut, User as UserIcon } from 'lucide-react';

interface NavbarProps {
  wsConnected: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ wsConnected }) => {
  const { user, role, switchRole, logout, login } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [emailInput, setEmailInput] = useState('driver@roadsentinel.io');
  const [passwordInput, setPasswordInput] = useState('driver123');

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(emailInput, passwordInput);
      setShowLoginModal(false);
    } catch (err) {
      alert('Login failed. Please check your credentials.');
    }
  };

  return (
    <>
      <header style={{
        height: '64px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: '1px solid var(--border-color)',
        background: 'rgba(11, 15, 25, 0.95)',
        backdropFilter: 'blur(12px)',
        zIndex: 1000,
        position: 'relative'
      }}>
        {/* Brand Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)'
          }}>
            <Shield size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px', fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
                ROAD<span style={{ color: '#818cf8' }}>Sentinel</span>
              </span>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(99, 102, 241, 0.2)',
                color: '#a5b4fc',
                border: '1px solid rgba(99, 102, 241, 0.4)'
              }}>v0.4 SPEC</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Spatial Road Hazard & Safety Platform</p>
          </div>
        </div>

        {/* Live WebSocket Status & Role Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Live WS Status Pill */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '20px',
            fontSize: '12px',
            fontWeight: 600,
            background: wsConnected ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            color: wsConnected ? '#4ade80' : '#f87171',
            border: wsConnected ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)'
          }}>
            {wsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
            <span>{wsConnected ? 'Real-time WebSocket Live' : 'Reconnecting...'}</span>
          </div>

          {/* Role Switcher Pill */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            background: 'rgba(31, 41, 55, 0.8)',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid var(--border-color)'
          }}>
            <button
              onClick={() => switchRole('driver')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 600,
                background: role === 'driver' ? 'var(--accent-primary)' : 'transparent',
                color: role === 'driver' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s'
              }}
            >
              <Navigation size={14} />
              Driver Mode
            </button>
            <button
              onClick={() => switchRole('admin')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 600,
                background: role === 'admin' || role === 'authority' ? '#a855f7' : 'transparent',
                color: role === 'admin' || role === 'authority' ? '#ffffff' : 'var(--text-secondary)',
                transition: 'all 0.2s'
              }}
            >
              <Activity size={14} />
              Admin / Authority
            </button>
          </div>

          {/* User Account / Profile */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '13px', fontWeight: 600, color: '#f3f4f6' }}>{user.name}</p>
                <span style={{ fontSize: '11px', color: '#9ca3af', textTransform: 'capitalize' }}>{user.role} role</span>
              </div>
              <button
                onClick={logout}
                title="Logout"
                style={{
                  padding: '8px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  background: 'rgba(31, 41, 55, 0.5)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer'
                }}
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowLoginModal(true)}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                background: 'var(--accent-primary)',
                color: '#ffffff',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <UserIcon size={14} />
              Login / Sign In
            </button>
          )}
        </div>
      </header>

      {/* Login Modal */}
      {showLoginModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2000
        }}>
          <div className="glass-panel" style={{ width: '380px', padding: '24px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>Sign In to ROADSentinel</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '20px' }}>Select role or enter credentials to switch perspective.</p>
            
            <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Email</label>
                <input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '6px',
                    background: '#1f2937',
                    border: '1px solid var(--border-color)',
                    color: '#ffffff',
                    fontSize: '14px'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Password</label>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '6px',
                    background: '#1f2937',
                    border: '1px solid var(--border-color)',
                    color: '#ffffff',
                    fontSize: '14px'
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => { setEmailInput('driver@roadsentinel.io'); setPasswordInput('driver123'); }}
                  style={{ flex: 1, padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#374151', color: '#fff', fontSize: '11px', cursor: 'pointer' }}
                >
                  Fill Driver
                </button>
                <button
                  type="button"
                  onClick={() => { setEmailInput('admin@roadsentinel.io'); setPasswordInput('admin123'); }}
                  style={{ flex: 1, padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', background: '#374151', color: '#fff', fontSize: '11px', cursor: 'pointer' }}
                >
                  Fill Admin
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => setShowLoginModal(false)}
                  style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'transparent', color: '#9ca3af', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ padding: '8px 20px', borderRadius: '6px', border: 'none', background: 'var(--accent-primary)', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
                >
                  Sign In
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
