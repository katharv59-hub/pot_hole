import React, { forwardRef } from 'react';

export type SurfaceLevel = 'workspace' | 'panel' | 'card' | 'hud' | 'modal';

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  level?: SurfaceLevel;
  interactive?: boolean;
  padded?: boolean;
}

const levelStyles: Record<SurfaceLevel, React.CSSProperties> = {
  workspace: {
    backgroundColor: 'var(--surface-workspace)',
    border: 'none',
  },
  panel: {
    backgroundColor: 'var(--surface-panel)',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-subtle)',
    borderRadius: 'var(--radius-md)',
  },
  card: {
    backgroundColor: 'var(--surface-card)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-subtle)',
    borderRadius: 'var(--radius-md)',
  },
  hud: {
    backgroundColor: 'var(--surface-overlay)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-overlay)',
    borderRadius: 'var(--radius-md)',
  },
  modal: {
    backgroundColor: 'var(--surface-modal)',
    border: '1px solid var(--border-strong)',
    boxShadow: 'var(--shadow-overlay)',
    borderRadius: 'var(--radius-lg)',
  },
};

export const Panel = forwardRef<HTMLDivElement, PanelProps>(
  ({ level = 'panel', interactive = false, padded = true, style, className = '', children, ...props }, ref) => {
    const baseStyle: React.CSSProperties = {
      ...levelStyles[level],
      padding: padded ? 'var(--space-4)' : '0',
      transition: interactive ? 'all var(--motion-normal)' : undefined,
      ...style,
    };

    const cls = [
      'rs-surface-container',
      interactive ? 'rs-panel-interactive' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div ref={ref} style={baseStyle} className={cls} {...props}>
        {children}
      </div>
    );
  }
);

Panel.displayName = 'Panel';

export const PanelHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  style,
  className = '',
  children,
  ...props
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 'var(--space-3)',
      paddingBottom: 'var(--space-3)',
      marginBottom: 'var(--space-3)',
      borderBottom: '1px solid var(--border-subtle)',
      ...style,
    }}
    className={`rs-panel-header ${className}`}
    {...props}
  >
    {children}
  </div>
);

export const PanelTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  style,
  className = '',
  children,
  ...props
}) => (
  <h3
    style={{
      fontSize: '14px',
      fontWeight: 600,
      color: 'var(--text-primary)',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      margin: 0,
      ...style,
    }}
    className={`rs-panel-title ${className}`}
    {...props}
  >
    {children}
  </h3>
);

export const PanelBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  style,
  className = '',
  children,
  ...props
}) => (
  <div style={{ flex: 1, ...style }} className={`rs-panel-body ${className}`} {...props}>
    {children}
  </div>
);

export const PanelFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  style,
  className = '',
  children,
  ...props
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 'var(--space-2)',
      paddingTop: 'var(--space-3)',
      marginTop: 'var(--space-3)',
      borderTop: '1px solid var(--border-subtle)',
      ...style,
    }}
    className={`rs-panel-footer ${className}`}
    {...props}
  >
    {children}
  </div>
);
