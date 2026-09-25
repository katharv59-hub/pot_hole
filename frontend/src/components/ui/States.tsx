import React from 'react';
import { Button } from './Button';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  style?: React.CSSProperties;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  style,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-8) var(--space-4)',
        textAlign: 'center',
        color: 'var(--text-tertiary)',
        ...style,
      }}
    >
      {icon && (
        <div
          style={{
            fontSize: '32px',
            marginBottom: 'var(--space-3)',
            opacity: 0.6,
            color: 'var(--text-secondary)',
          }}
        >
          {icon}
        </div>
      )}
      <h4
        style={{
          fontSize: '15px',
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: '4px',
        }}
      >
        {title}
      </h4>
      {description && (
        <p
          style={{
            fontSize: '13px',
            color: 'var(--text-secondary)',
            maxWidth: '380px',
            marginBottom: actionLabel ? 'var(--space-4)' : 0,
            lineHeight: 1.5,
          }}
        >
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};

export interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  style?: React.CSSProperties;
}

export const LoadingState: React.FC<LoadingStateProps> = ({ message = 'Loading telemetry...', size = 'md', style }) => {
  const spinnerSize = size === 'sm' ? '16px' : size === 'lg' ? '32px' : '22px';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-3)',
        padding: 'var(--space-8)',
        color: 'var(--text-secondary)',
        fontSize: '13px',
        ...style,
      }}
    >
      <div
        style={{
          width: spinnerSize,
          height: spinnerSize,
          border: '2px solid rgba(255, 255, 255, 0.1)',
          borderTopColor: 'var(--accent-primary)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      {message && <span>{message}</span>}
    </div>
  );
};

export interface ErrorStateProps {
  title?: string;
  error?: string;
  onRetry?: () => void;
  style?: React.CSSProperties;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load telemetry',
  error,
  onRetry,
  style,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-6)',
        backgroundColor: 'rgba(239, 68, 68, 0.08)',
        border: '1px solid rgba(239, 68, 68, 0.25)',
        borderRadius: 'var(--radius-md)',
        textAlign: 'center',
        ...style,
      }}
    >
      <h4 style={{ fontSize: '14px', fontWeight: 600, color: '#f87171', marginBottom: '4px' }}>
        {title}
      </h4>
      {error && (
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
          {error}
        </p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry Connection
        </Button>
      )}
    </div>
  );
};
