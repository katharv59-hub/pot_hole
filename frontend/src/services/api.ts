import axios from 'axios';
import {
  ConfigBundle, RoadEvent, Report, Device,
  AnalyticsSummary, RouteSafetyResponse, User
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatically inject user Bearer token if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('roadsentinel_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const fetchConfigBundle = async (): Promise<ConfigBundle> => {
  const res = await api.get<ConfigBundle>('/config/bundle');
  return res.data;
};

export const fetchRoadEvents = async (bbox?: string, eventType?: string, status?: string): Promise<RoadEvent[]> => {
  const params: Record<string, string> = {};
  if (bbox) params.bbox = bbox;
  if (eventType) params.event_type = eventType;
  if (status) params.status = status;
  const res = await api.get<RoadEvent[]>('/events', { params });
  return res.data;
};

export const updateEventStatus = async (eventId: string, status: string): Promise<RoadEvent> => {
  const res = await api.patch<RoadEvent>(`/admin/events/${eventId}/status`, { status });
  return res.data;
};

export const createReport = async (data: { latitude: number; longitude: number; description?: string }): Promise<Report> => {
  const res = await api.post<Report>('/reports', data);
  return res.data;
};

export const fetchMyReports = async (): Promise<Report[]> => {
  const res = await api.get<Report[]>('/reports/me');
  return res.data;
};

export const fetchAllReports = async (): Promise<Report[]> => {
  const res = await api.get<Report[]>('/reports/admin');
  return res.data;
};

export const getReportUploadUrl = async (reportId: string) => {
  const res = await api.post<{ media_id: string; upload_url: string }>(`/reports/${reportId}/media/upload-url`);
  return res.data;
};

export const confirmReportMedia = async (reportId: string, mediaId: string) => {
  const res = await api.post(`/reports/${reportId}/media/${mediaId}/confirm`);
  return res.data;
};

export const fetchDevices = async (): Promise<Device[]> => {
  const res = await api.get<Device[]>('/devices');
  return res.data;
};

export const registerDevice = async (data: { hardware_type: string; vehicle_id?: string }) => {
  const res = await api.post('/devices/register', data);
  return res.data;
};

export const provisionDevice = async (deviceId: string, provisioningSecret: string) => {
  const res = await api.post(`/devices/${deviceId}/provision`, { provisioning_secret: provisioningSecret });
  return res.data;
};

export const reassignDevice = async (deviceId: string, newVehicleId: string) => {
  const res = await api.post(`/devices/${deviceId}/reassign`, { new_vehicle_id: newVehicleId });
  return res.data;
};

export const checkRouteSafety = async (
  polyline?: [number, number][],
  origin?: string,
  destination?: string
): Promise<RouteSafetyResponse> => {
  const params: Record<string, string> = {};
  if (origin) params.origin = origin;
  if (destination) params.destination = destination;
  const res = await api.post<RouteSafetyResponse>('/routes/safety', { polyline: polyline || [] }, { params });
  return res.data;
};

export const fetchAnalyticsSummary = async (): Promise<AnalyticsSummary> => {
  const res = await api.get<AnalyticsSummary>('/analytics/summary');
  return res.data;
};
