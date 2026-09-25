import React from 'react';

export interface MetricProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  delta?: {
    value: string | number;
    trend: 'up' | 'down' | 'neutral';
  };
  icon?: React.ReactNode;
  statusColor?: string;
  subtext?: string;
  compact?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export const Metric: React.FC<MetricProps> = ({
  label,
  value,
  unit,
  delta,
  icon,
  statusColor,
  subtext,
  compact = false,
  className = '',
  style,
}) => {
  return (
    <div
      className={`rs-panel rs-metric-card ${className}`}
      style={{
        padding: compact ? 'var(--space-3)' : 'var(--space-4)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        position: 'relative',
        overflow: 'hidden',
        borderLeft: statusColor ? `3px solid ${statusColor}` : undefined,
        ...style,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--text-tertiary)',
          }}
        >
          {label}
        </span>
        {icon && (
          <span style={{ color: statusColor || 'var(--text-secondary)', display: 'flex', opacity: 0.8 }}>
            {icon}
          </span>
        )}
      </div>

      <div style={{ marginTop: '8px', display: 'flex', alignItems: 'baseline', gap: '6px' }}>
        <span
          className="telemetry-numeric"
          style={{
            fontSize: compact ? '20px' : '26px',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'var(--text-primary)',
          }}
        >
          {value}
        </span>
        {unit && (
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-tertiary)' }}>{unit}</span>
        )}
      </div>

      {(delta || subtext) && (
        <div
          style={{
            marginTop: '6px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            color: 'var(--text-secondary)',
          }}
        >
          {delta && (
            <span
              style={{
                fontWeight: 600,
                color:
                  delta.trend === 'up'
                    ? '#4ade80'
                    : delta.trend === 'down'
                    ? '#f87171'
                    : 'var(--text-tertiary)',
              }}
            >
              {delta.trend === 'up' ? '↑ ' : delta.trend === 'down' ? '↓ ' : ''}
              {delta.value}
            </span>
          )}
          {subtext && <span>{subtext}</span>}
        </div>
      )}
    </div>
  );
};
