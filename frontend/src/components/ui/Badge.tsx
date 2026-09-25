import React from 'react';

export type BadgeVariant = 'neutral' | 'info' | 'success' | 'warning' | 'destructive' | 'outline';
export type BadgeSize = 'sm' | 'md';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  icon?: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, React.CSSProperties> = {
  neutral: {
    backgroundColor: 'rgba(148, 163, 184, 0.12)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-subtle)',
  },
  info: {
    backgroundColor: 'rgba(59, 130, 246, 0.12)',
    color: '#60a5fa',
    border: '1px solid rgba(59, 130, 246, 0.28)',
  },
  success: {
    backgroundColor: 'rgba(34, 197, 94, 0.12)',
    color: '#4ade80',
    border: '1px solid rgba(34, 197, 94, 0.28)',
  },
  warning: {
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    color: '#fbbf24',
    border: '1px solid rgba(245, 158, 11, 0.28)',
  },
  destructive: {
    backgroundColor: 'rgba(239, 68, 68, 0.14)',
    color: '#f87171',
    border: '1px solid rgba(239, 68, 68, 0.35)',
  },
  outline: {
    backgroundColor: 'transparent',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
  },
};

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  icon,
  children,
  style,
  className = '',
  ...props
}) => {
  const isSm = size === 'sm';
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: isSm ? '1px 6px' : '2px 8px',
    fontSize: isSm ? '10px' : '11px',
    fontWeight: 600,
    letterSpacing: '0.02em',
    borderRadius: 'var(--radius-xs)',
    whiteSpace: 'nowrap',
    ...variantStyles[variant],
    ...style,
  };

  return (
    <span style={baseStyle} className={`rs-badge ${className}`} {...props}>
      {icon}
      {children}
    </span>
  );
};
