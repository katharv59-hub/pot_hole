import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConfigBundle, EventTypeConfig, SeverityScaleConfig, VehicleTypeConfig } from '../types';
import { fetchConfigBundle } from '../services/api';

interface ConfigContextType {
  config: ConfigBundle | null;
  loading: boolean;
  getSeverityColor: (severity: number) => string;
  getSeverityBg: (severity: number) => string;
  getSeverityLabel: (severity: number) => string;
  getEventTypeLabel: (key: string) => string;
  getEventTypeIcon: (key: string) => string;
}

const DEFAULT_SEVERITY_SCALE: SeverityScaleConfig = {
  min_val: 0.0,
  max_val: 1.0,
  buckets: {
    low: { min: 0.0, max: 0.35, color: '#22c55e', label: 'Low', bg: 'rgba(34, 197, 94, 0.15)' },
    medium: { min: 0.35, max: 0.60, color: '#eab308', label: 'Medium', bg: 'rgba(234, 179, 8, 0.15)' },
    high: { min: 0.60, max: 0.80, color: '#f97316', label: 'High', bg: 'rgba(249, 115, 22, 0.15)' },
    critical: { min: 0.80, max: 1.00, color: '#ef4444', label: 'Critical', bg: 'rgba(239, 68, 68, 0.15)' },
  },
};

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

export const ConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<ConfigBundle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchConfigBundle()
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load dynamic configuration bundle:', err);
        setLoading(false);
      });
  }, []);

  const getSeverityColor = (severity: number): string => {
    const buckets = config?.severity_scale?.buckets || DEFAULT_SEVERITY_SCALE.buckets;
    if (severity >= 0.80) return buckets.critical?.color || '#ef4444';
    if (severity >= 0.60) return buckets.high?.color || '#f97316';
    if (severity >= 0.35) return buckets.medium?.color || '#eab308';
    return buckets.low?.color || '#22c55e';
  };

  const getSeverityBg = (severity: number): string => {
    const buckets = config?.severity_scale?.buckets || DEFAULT_SEVERITY_SCALE.buckets;
    if (severity >= 0.80) return buckets.critical?.bg || 'rgba(239, 68, 68, 0.15)';
    if (severity >= 0.60) return buckets.high?.bg || 'rgba(249, 115, 22, 0.15)';
    if (severity >= 0.35) return buckets.medium?.bg || 'rgba(234, 179, 8, 0.15)';
    return buckets.low?.bg || 'rgba(34, 197, 94, 0.15)';
  };

  const getSeverityLabel = (severity: number): string => {
    if (severity >= 0.80) return 'Critical';
    if (severity >= 0.60) return 'High';
    if (severity >= 0.35) return 'Medium';
    return 'Low';
  };

  const getEventTypeLabel = (key: string): string => {
    const match = config?.event_types?.find((t) => t.key === key);
    return match ? match.label : key.replace('_', ' ').toUpperCase();
  };

  const getEventTypeIcon = (key: string): string => {
    const match = config?.event_types?.find((t) => t.key === key);
    return match ? match.icon : 'alert-circle';
  };

  return (
    <ConfigContext.Provider
      value={{
        config,
        loading,
        getSeverityColor,
        getSeverityBg,
        getSeverityLabel,
        getEventTypeLabel,
        getEventTypeIcon,
      }}
    >
      {children}
    </ConfigContext.Provider>
  );
};

export const useConfig = () => {
  const context = useContext(ConfigContext);
  if (!context) {
    throw new Error('useConfig must be used within a ConfigProvider');
  }
  return context;
};
