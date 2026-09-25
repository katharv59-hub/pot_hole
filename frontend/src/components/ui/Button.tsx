import React, { forwardRef } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    backgroundColor: 'var(--accent-primary)',
    color: '#ffffff',
    border: '1px solid var(--accent-primary)',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3)',
  },
  secondary: {
    backgroundColor: 'var(--surface-input)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-default)',
  },
  outline: {
    backgroundColor: 'transparent',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
  },
  ghost: {
    backgroundColor: 'transparent',
    color: 'var(--text-secondary)',
    border: '1px solid transparent',
  },
  destructive: {
    backgroundColor: 'rgba(239, 68, 68, 0.16)',
    color: '#f87171',
    border: '1px solid rgba(239, 68, 68, 0.4)',
  },
};

const sizeStyles: Record<ButtonSize, { padding: string; fontSize: string; height: string }> = {
  sm: {
    padding: '0 10px',
    fontSize: '12px',
    height: '30px',
  },
  md: {
    padding: '0 16px',
    fontSize: '13px',
    height: '38px',
  },
  lg: {
    padding: '0 20px',
    fontSize: '14px',
    height: '44px',
  },
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'secondary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      style,
      className = '',
      ...props
    },
    ref
  ) => {
    const baseStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '6px',
      borderRadius: 'var(--radius-sm)',
      fontWeight: 500,
      cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
      opacity: disabled || isLoading ? 0.6 : 1,
      transition: 'all var(--motion-fast)',
      fontFamily: 'inherit',
      textDecoration: 'none',
      whiteSpace: 'nowrap',
      ...sizeStyles[size],
      ...variantStyles[variant],
      ...style,
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        style={baseStyle}
        className={`rs-button ${className}`}
        {...props}
      >
        {isLoading ? (
          <span
            style={{
              display: 'inline-block',
              width: '14px',
              height: '14px',
              border: '2px solid currentColor',
              borderRightColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 0.75s linear infinite',
            }}
          />
        ) : (
          leftIcon
        )}
        {children}
        {!isLoading && rightIcon}
      </button>
    );
  }
);

Button.displayName = 'Button';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon: React.ReactNode;
  'aria-label': string;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ variant = 'ghost', size = 'md', icon, style, className = '', ...props }, ref) => {
    const sizeDimensions: Record<ButtonSize, { width: string; height: string; fontSize: string }> = {
      sm: { width: '30px', height: '30px', fontSize: '13px' },
      md: { width: '38px', height: '38px', fontSize: '16px' },
      lg: { width: '44px', height: '44px', fontSize: '18px' },
    };

    const baseStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: 'var(--radius-sm)',
      cursor: props.disabled ? 'not-allowed' : 'pointer',
      opacity: props.disabled ? 0.5 : 1,
      transition: 'all var(--motion-fast)',
      ...sizeDimensions[size],
      ...variantStyles[variant],
      ...style,
    };

    return (
      <button ref={ref} style={baseStyle} className={`rs-icon-button ${className}`} {...props}>
        {icon}
      </button>
    );
  }
);

IconButton.displayName = 'IconButton';
