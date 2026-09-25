import React from 'react';

export type OperationalStatus =
  | 'verified'
  | 'unverified'
  | 'resolved'
  | 'duplicate'
  | 'active'
  | 'inactive'
  | 'online'
  | 'offline'
  | 'pending';

export interface StatusBadgeProps {
  status: OperationalStatus | string;
  size?: 'sm' | 'md';
  showDot?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const statusConfig: Record<string, { color: string; bg: string; label: string }> = {
  verified: { color: '#60a5fa', bg: 'rgba(59, 130, 246, 0.12)', label: 'Verified' },
  unverified: { color: '#fbbf24', bg: 'rgba(245, 158, 11, 0.12)', label: 'Unverified' },
  resolved: { color: '#818cf8', bg: 'rgba(99, 102, 241, 0.12)', label: 'Resolved' },
  duplicate: { color: '#c084fc', bg: 'rgba(168, 85, 247, 0.12)', label: 'Duplicate' },
  active: { color: '#4ade80', bg: 'rgba(34, 197, 94, 0.12)', label: 'Active' },
  online: { color: '#4ade80', bg: 'rgba(34, 197, 94, 0.12)', label: 'Online' },
  inactive: { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)', label: 'Inactive' },
  offline: { color: '#f87171', bg: 'rgba(239, 68, 68, 0.12)', label: 'Offline' },
  pending: { color: '#fbbf24', bg: 'rgba(245, 158, 11, 0.12)', label: 'Pending' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  showDot = true,
  className = '',
  style,
}) => {
  const normStatus = status.toLowerCase();
  const conf = statusConfig[normStatus] || {
    color: '#94a3b8',
    bg: 'rgba(148, 163, 184, 0.12)',
    label: status.toUpperCase(),
  };

  const isSm = size === 'sm';

  return (
    <span
      className={`rs-status-badge ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: isSm ? '1px 6px' : '2px 8px',
        fontSize: isSm ? '10px' : '11px',
        fontWeight: 600,
        letterSpacing: '0.02em',
        borderRadius: 'var(--radius-xs)',
        backgroundColor: conf.bg,
        color: conf.color,
        border: `1px solid ${conf.color}33`,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {showDot && (
        <span
          style={{
            width: isSm ? '4px' : '5px',
            height: isSm ? '4px' : '5px',
            borderRadius: '50%',
            backgroundColor: conf.color,
            display: 'inline-block',
          }}
        />
      )}
      <span>{conf.label}</span>
    </span>
  );
};
