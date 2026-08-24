export type UserRole = 'driver' | 'admin' | 'authority';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  saved_locations?: Array<{ name: string; latitude: number; longitude: number }>;
}

export interface EventTypeConfig {
  key: string;
  label: string;
  icon: string;
  description: string;
}

export interface SeverityBucket {
  min: number;
  max: number;
  color: string;
  label: string;
  bg: string;
}

export interface SeverityScaleConfig {
  min_val: number;
  max_val: number;
  buckets: Record<string, SeverityBucket>;
}

export interface VehicleTypeConfig {
  key: string;
  label: string;
  icon: string;
}

export interface ConfigBundle {
  event_types: EventTypeConfig[];
  severity_scale: SeverityScaleConfig;
  vehicle_types: VehicleTypeConfig[];
}

export interface MediaAsset {
  id: string;
  event_id?: string;
  report_id?: string;
  type: string;
  storage_url: string;
  captured_at: string;
  retention_expires_at?: string;
  access_tier: 'raw' | 'processed';
}

export interface MLPrediction {
  id: string;
  modality: 'imu' | 'camera' | 'fused';
  model_name: string;
  model_version: string;
  predicted_type: string;
  confidence: number;
  inference_location: 'edge' | 'cloud';
  fused_from?: string[];
}

export interface RoadEvent {
  id: string;
  device_event_id: string;
  device_id: string;
  vehicle_id: string;
  device_timestamp: string;
  server_timestamp: string;
  latitude: number;
  longitude: number;
  location_accuracy_m?: number;
  location_source: string;
  road_segment_id?: string;
  event_type: string;
  modality_sources: string[];
  confidence: number;
  severity: number;
  severity_label: 'low' | 'medium' | 'high' | 'critical';
  status: 'unverified' | 'verified' | 'duplicate' | 'resolved';
  schema_version: string;
  firmware_version: string;
  corroboration_count: number;
  media_assets?: MediaAsset[];
  ml_predictions?: MLPrediction[];
}

export interface Report {
  id: string;
  user_id: string;
  event_id?: string;
  description?: string;
  latitude: number;
  longitude: number;
  status: 'pending' | 'verified' | 'resolved';
  created_at: string;
  media_assets?: MediaAsset[];
}

export interface Device {
  id: string;
  vehicle_id?: string;
  hardware_type: string;
  firmware_version: string;
  status: 'provisioning' | 'active' | 'disabled' | 'revoked';
  last_seen_at?: string;
  created_at: string;
}

export interface AnalyticsSummary {
  metrics: {
    total_events: number;
    unverified_count: number;
    verified_count: number;
    resolved_count: number;
    duplicate_count: number;
    active_devices: number;
    total_devices: number;
    total_manual_reports: number;
  };
  event_type_distribution: Record<string, number>;
  severity_distribution: Record<string, number>;
}

export interface RouteSafetyResponse {
  overall_safety_score: number;
  scored_segments_count: number;
  unscored_stretches_count: number;
  detected_hazards_on_route: RoadEvent[];
  segment_scores: Array<{
    segment_index: number;
    start_point: [number, number];
    end_point: [number, number];
    is_road_network_scored: boolean;
    framing_label: string;
    local_safety_score: number;
  }>;
}
