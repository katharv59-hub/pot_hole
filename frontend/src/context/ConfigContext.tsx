import React, { createContext, useContext } from 'react';
import { ConfigBundle, SeverityBucket, SeverityScaleConfig } from '../types';
import { useConfigBundle } from '../hooks/useConfigBundle';

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

const findMatchingBucket = (
  severity: number,
  buckets: Record<string, SeverityBucket>
): SeverityBucket | null => {
  // Normalize severity to 0.0 - 1.0 range
  const normalized = Math.max(0.0, Math.min(1.0, severity));

  // Find bucket where normalized severity falls between min and max
  for (const bucket of Object.values(buckets)) {
    // Include min and max boundaries gracefully
    if (normalized >= bucket.min && normalized <= bucket.max) {
      return bucket;
    }
  }

  // Fallback to highest bucket if >= max or lowest if <= min
  const bucketList = Object.values(buckets).sort((a, b) => a.min - b.min);
  if (bucketList.length > 0) {
    if (normalized >= bucketList[bucketList.length - 1].max) {
      return bucketList[bucketList.length - 1];
    }
    return bucketList[0];
  }

  return null;
};

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

export const ConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: config = null, isLoading } = useConfigBundle();

  const getSeverityColor = (severity: number): string => {
    const buckets = config?.severity_scale?.buckets || DEFAULT_SEVERITY_SCALE.buckets;
    const match = findMatchingBucket(severity, buckets);
    return match?.color || '#ef4444';
  };

  const getSeverityBg = (severity: number): string => {
    const buckets = config?.severity_scale?.buckets || DEFAULT_SEVERITY_SCALE.buckets;
    const match = findMatchingBucket(severity, buckets);
    return match?.bg || 'rgba(239, 68, 68, 0.15)';
  };

  const getSeverityLabel = (severity: number): string => {
    const buckets = config?.severity_scale?.buckets || DEFAULT_SEVERITY_SCALE.buckets;
    const match = findMatchingBucket(severity, buckets);
    return match?.label || 'Alert';
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
        config: config || null,
        loading: isLoading,
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
