import React from 'react';
import { useConfig } from '../../context/ConfigContext';

export interface SeverityBadgeProps {
  severity: number;
  showScore?: boolean;
  pulseOnCritical?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  style?: React.CSSProperties;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  showScore = false,
  pulseOnCritical = false,
  size = 'md',
  className = '',
  style,
}) => {
  const { getSeverityColor, getSeverityBg, getSeverityLabel } = useConfig();

  const color = getSeverityColor(severity);
  const bg = getSeverityBg(severity);
  const label = getSeverityLabel(severity);
  const isCritical = label.toLowerCase() === 'critical';

  const isSm = size === 'sm';
  const isLg = size === 'lg';

  const basePadding = isSm ? '1px 6px' : isLg ? '4px 12px' : '2px 8px';
  const fontSize = isSm ? '10px' : isLg ? '13px' : '11px';

  return (
    <span
      className={`rs-severity-badge ${className}`}
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: basePadding,
        fontSize,
        fontWeight: 700,
        letterSpacing: '0.03em',
        textTransform: 'uppercase',
        borderRadius: 'var(--radius-xs)',
        backgroundColor: bg,
        color: color,
        border: `1px solid ${color}4d`,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {pulseOnCritical && isCritical && <span className="critical-pulse-ring" />}
      <span
        style={{
          width: isSm ? '5px' : '6px',
          height: isSm ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: color,
          display: 'inline-block',
          boxShadow: `0 0 6px ${color}`,
        }}
      />
      <span>{label}</span>
      {showScore && (
        <span
          className="font-mono"
          style={{
            opacity: 0.85,
            fontWeight: 500,
            fontSize: isSm ? '9px' : '10px',
            marginLeft: '2px',
          }}
        >
          ({(severity * 100).toFixed(0)}%)
        </span>
      )}
    </span>
  );
};
