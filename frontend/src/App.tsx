import React, { useEffect, useState, useRef, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ConfigProvider } from './context/ConfigContext';
import { Navbar } from './components/Navbar';
import { DriverDashboard } from './components/Driver/DriverDashboard';
import { AdminDashboard } from './components/Admin/AdminDashboard';
import { wsClient } from './services/websocket';
import { fetchRoadEvents } from './services/api';
import { useQueryClient } from '@tanstack/react-query';

const MainApp: React.FC = () => {
  const { role, token } = useAuth();
  const [wsConnected, setWsConnected] = useState(false);
  const currentBboxRef = useRef<[number, number, number, number] | null>(null);
  const queryClient = useQueryClient();

  // Track the current map bbox for reconnect reconciliation
  const handleBboxChange = useCallback((bbox: [number, number, number, number]) => {
    currentBboxRef.current = bbox;
  }, []);

  useEffect(() => {
    // Only connect when authenticated token is available
    if (!token) {
      return;
    }

    wsClient.connect(token);

    // Register reconnect reconciliation handler
    const unsubReconnect = wsClient.onReconnect(() => {
      // On reconnect: fetch authoritative events via REST to reconcile state
      const bbox = currentBboxRef.current;
      if (bbox) {
        const bboxStr = `${bbox[0]},${bbox[1]},${bbox[2]},${bbox[3]}`;
        fetchRoadEvents(bboxStr)
          .then(() => {
            // Invalidate TanStack Query cache to force refetch with fresh data
            queryClient.invalidateQueries({ queryKey: ['roadEvents'] });
          })
          .catch((err) => console.error('Reconnect reconciliation failed:', err));
      } else {
        // No bbox available — just invalidate query cache
        queryClient.invalidateQueries({ queryKey: ['roadEvents'] });
      }
    });

    const checkInterval = setInterval(() => {
      setWsConnected(wsClient.getStatus());
    }, 2000);

    return () => {
      clearInterval(checkInterval);
      unsubReconnect();
    };
  }, [token, queryClient]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', backgroundColor: 'var(--bg-primary)' }}>
      <Navbar wsConnected={wsConnected} />
      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {role === 'driver' ? (
          <DriverDashboard onBboxChange={handleBboxChange} />
        ) : (
          <AdminDashboard />
        )}
      </main>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <ConfigProvider>
        <MainApp />
      </ConfigProvider>
    </AuthProvider>
  );
}
