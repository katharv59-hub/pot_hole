import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ConfigProvider } from './context/ConfigContext';
import { Navbar } from './components/Navbar';
import { DriverDashboard } from './components/Driver/DriverDashboard';
import { AdminDashboard } from './components/Admin/AdminDashboard';
import { wsClient } from './services/websocket';

const MainApp: React.FC = () => {
  const { role } = useAuth();
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    wsClient.connect();

    const checkInterval = setInterval(() => {
      setWsConnected(wsClient.getStatus());
    }, 1000);

    return () => clearInterval(checkInterval);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', backgroundColor: 'var(--bg-primary)' }}>
      <Navbar wsConnected={wsConnected} />
      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {role === 'driver' ? <DriverDashboard /> : <AdminDashboard />}
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
