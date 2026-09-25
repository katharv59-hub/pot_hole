import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, Navigation, Activity, Wifi, WifiOff, LogOut, User as UserIcon, X } from 'lucide-react';
import { Button, IconButton, Panel, Input } from './ui';

interface NavbarProps {
  wsConnected: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ wsConnected }) => {
  const { user, role, switchRole, logout, login } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [emailInput, setEmailInput] = useState('driver@roadsentinel.io');
  const [passwordInput, setPasswordInput] = useState('driver123');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await login(emailInput, passwordInput);
      setShowLoginModal(false);
    } catch {
      alert('Login failed. Please check your credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <header
        style={{
          height: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 var(--space-6)',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--surface-workspace)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          zIndex: 1000,
          position: 'relative',
        }}
      >
        {/* Brand Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: 'var(--radius-sm)',
              background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 12px rgba(99, 102, 241, 0.35)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
            }}
          >
            <Shield size={18} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '16px',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.02em',
                  fontFamily: 'Outfit, sans-serif',
                }}
              >
                ROAD<span style={{ color: 'var(--accent-primary)' }}>Sentinel</span>
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-xs)',
                  background: 'rgba(99, 102, 241, 0.15)',
                  color: 'var(--accent-cyan)',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                  letterSpacing: '0.04em',
                }}
              >
                COMMAND v0.4
              </span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: 400 }}>
              Spatial Road Hazard & Fleet Infrastructure
            </p>
          </div>
        </div>

        {/* Live WebSocket Status & Role Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          {/* Live WS Status Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: 'var(--radius-pill)',
              fontSize: '11px',
              fontWeight: 600,
              background: wsConnected ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              color: wsConnected ? 'var(--severity-low)' : 'var(--severity-critical)',
              border: wsConnected
                ? '1px solid rgba(34, 197, 94, 0.3)'
                : '1px solid rgba(239, 68, 68, 0.3)',
            }}
          >
            {wsConnected ? (
              <>
                <span className="live-status-dot" style={{ width: '6px', height: '6px' }} />
                <Wifi size={13} />
                <span>TELEMETRY STREAM LIVE</span>
              </>
            ) : (
              <>
                <WifiOff size={13} />
                <span>RECONNECTING FEED</span>
              </>
            )}
          </div>

          {/* Role Switcher Switch */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--surface-input)',
              padding: '2px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-default)',
            }}
          >
            <Button
              variant={role === 'driver' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => switchRole('driver')}
              leftIcon={<Navigation size={13} />}
              style={{
                height: '28px',
                fontSize: '12px',
                padding: '0 12px',
                borderRadius: '4px',
              }}
            >
              Driver View
            </Button>
            <Button
              variant={role === 'admin' || role === 'authority' ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => switchRole('admin')}
              leftIcon={<Activity size={13} />}
              style={{
                height: '28px',
                fontSize: '12px',
                padding: '0 12px',
                borderRadius: '4px',
              }}
            >
              Authority View
            </Button>
          </div>

          {/* User Account / Profile */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {user.name}
                </p>
                <span
                  style={{
                    fontSize: '10px',
                    color: 'var(--text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    fontWeight: 600,
                  }}
                >
                  {user.role}
                </span>
              </div>
              <IconButton
                variant="secondary"
                size="sm"
                icon={<LogOut size={14} />}
                onClick={logout}
                aria-label="Logout"
                title="Logout"
              />
            </div>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowLoginModal(true)}
              leftIcon={<UserIcon size={14} />}
            >
              Sign In
            </Button>
          )}
        </div>
      </header>

      {/* Login Modal */}
      {showLoginModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(8, 12, 21, 0.85)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
          }}
        >
          <Panel
            level="modal"
            style={{ width: '400px', padding: 'var(--space-6)', position: 'relative' }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 'var(--space-2)',
              }}
            >
              <h3 style={{ fontSize: '16px', fontWeight: 700 }}>ROADSentinel Authentication</h3>
              <IconButton
                size="sm"
                variant="ghost"
                icon={<X size={16} />}
                aria-label="Close modal"
                onClick={() => setShowLoginModal(false)}
              />
            </div>
            <p
              style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-5)',
              }}
            >
              Enter credentials to switch operational role.
            </p>

            <form
              onSubmit={handleLoginSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
            >
              <Input
                label="Email"
                type="email"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                required
              />

              <Input
                label="Password"
                type="password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                required
              />

              <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: '4px' }}>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  style={{ flex: 1 }}
                  onClick={() => {
                    setEmailInput('driver@roadsentinel.io');
                    setPasswordInput('driver123');
                  }}
                >
                  Preset: Driver
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  style={{ flex: 1 }}
                  onClick={() => {
                    setEmailInput('admin@roadsentinel.io');
                    setPasswordInput('admin123');
                  }}
                >
                  Preset: Authority
                </Button>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 'var(--space-2)',
                  marginTop: 'var(--space-3)',
                }}
              >
                <Button
                  type="button"
                  variant="ghost"
                  size="md"
                  onClick={() => setShowLoginModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="md" isLoading={isSubmitting}>
                  Authenticate
                </Button>
              </div>
            </form>
          </Panel>
        </div>
      )}
    </>
  );
};
