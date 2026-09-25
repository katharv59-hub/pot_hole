import React, { forwardRef } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, leftIcon, rightIcon, id, style, className = '', disabled, ...props }, ref) => {
    const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              fontSize: '12px',
              fontWeight: 500,
              color: error ? '#f87171' : 'var(--text-secondary)',
            }}
          >
            {label}
          </label>
        )}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          {leftIcon && (
            <span
              style={{
                position: 'absolute',
                left: '10px',
                color: 'var(--text-tertiary)',
                display: 'flex',
                alignItems: 'center',
                pointerEvents: 'none',
              }}
            >
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            style={{
              width: '100%',
              height: '38px',
              padding: leftIcon ? '0 12px 0 34px' : rightIcon ? '0 34px 0 12px' : '0 12px',
              fontSize: '13px',
              backgroundColor: 'var(--surface-input)',
              color: 'var(--text-primary)',
              border: error ? '1px solid #ef4444' : '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              outline: 'none',
              opacity: disabled ? 0.6 : 1,
              cursor: disabled ? 'not-allowed' : 'text',
              ...style,
            }}
            className={`rs-input ${className}`}
            {...props}
          />
          {rightIcon && (
            <span
              style={{
                position: 'absolute',
                right: '10px',
                color: 'var(--text-tertiary)',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {rightIcon}
            </span>
          )}
        </div>
        {error ? (
          <span style={{ fontSize: '11px', color: '#f87171' }}>{error}</span>
        ) : helperText ? (
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{helperText}</span>
        ) : null}
      </div>
    );
  }
);

Input.displayName = 'Input';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
  options?: Array<{ value: string; label: string }>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, helperText, options, id, children, style, className = '', disabled, ...props }, ref) => {
    const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
        {label && (
          <label
            htmlFor={selectId}
            style={{
              fontSize: '12px',
              fontWeight: 500,
              color: error ? '#f87171' : 'var(--text-secondary)',
            }}
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          disabled={disabled}
          style={{
            width: '100%',
            height: '38px',
            padding: '0 12px',
            fontSize: '13px',
            backgroundColor: 'var(--surface-input)',
            color: 'var(--text-primary)',
            border: error ? '1px solid #ef4444' : '1px solid var(--border-default)',
            borderRadius: 'var(--radius-sm)',
            outline: 'none',
            opacity: disabled ? 0.6 : 1,
            cursor: disabled ? 'not-allowed' : 'pointer',
            ...style,
          }}
          className={`rs-select ${className}`}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        {error ? (
          <span style={{ fontSize: '11px', color: '#f87171' }}>{error}</span>
        ) : helperText ? (
          <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{helperText}</span>
        ) : null}
      </div>
    );
  }
);

Select.displayName = 'Select';
