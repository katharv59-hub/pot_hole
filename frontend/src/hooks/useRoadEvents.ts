import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchRoadEvents } from '../services/api';
import { RoadEvent } from '../types';

export const ROAD_EVENTS_QUERY_KEY = ['roadEvents'] as const;

export function useRoadEvents(bbox?: string, eventType?: string, status?: string) {
  return useQuery<RoadEvent[]>({
    queryKey: [...ROAD_EVENTS_QUERY_KEY, bbox, eventType, status],
    queryFn: () => fetchRoadEvents(bbox, eventType, status),
    staleTime: 30 * 1000, // 30 seconds — events change frequently
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to get a function that invalidates road events queries.
 * Useful for WebSocket event handlers to trigger refetch.
 */
export function useInvalidateRoadEvents() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ROAD_EVENTS_QUERY_KEY });
}
