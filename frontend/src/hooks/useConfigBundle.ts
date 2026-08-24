import { useQuery } from '@tanstack/react-query';
import { fetchConfigBundle } from '../services/api';
import { ConfigBundle } from '../types';

export const CONFIG_QUERY_KEY = ['configBundle'] as const;

export function useConfigBundle() {
  return useQuery<ConfigBundle>({
    queryKey: CONFIG_QUERY_KEY,
    queryFn: fetchConfigBundle,
    staleTime: 5 * 60 * 1000, // 5 minutes — config rarely changes
    retry: 2,
    refetchOnWindowFocus: false,
  });
}
