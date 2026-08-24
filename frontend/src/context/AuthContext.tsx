import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  role: UserRole;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, role: UserRole) => Promise<void>;
  logout: () => void;
  switchRole: (newRole: UserRole) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('roadsentinel_token'));
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('roadsentinel_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [role, setRole] = useState<UserRole>(user?.role || 'driver');

  useEffect(() => {
    if (token) {
      api.get('/auth/me')
        .then((res) => {
          setUser(res.data);
          setRole(res.data.role);
          localStorage.setItem('roadsentinel_user', JSON.stringify(res.data));
        })
        .catch(() => {
          logout();
        });
    }
  }, [token]);

  const login = async (email: string, password: string) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = res.data;
    setToken(access_token);
    setUser(userData);
    setRole(userData.role);
    localStorage.setItem('roadsentinel_token', access_token);
    localStorage.setItem('roadsentinel_user', JSON.stringify(userData));
  };

  const register = async (email: string, password: string, name: string, reqRole: UserRole) => {
    const res = await api.post('/auth/register', { email, password, name, role: reqRole });
    const { access_token, user: userData } = res.data;
    setToken(access_token);
    setUser(userData);
    setRole(userData.role);
    localStorage.setItem('roadsentinel_token', access_token);
    localStorage.setItem('roadsentinel_user', JSON.stringify(userData));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setRole('driver');
    localStorage.removeItem('roadsentinel_token');
    localStorage.removeItem('roadsentinel_user');
  };

  const switchRole = (newRole: UserRole) => {
    setRole(newRole);
    if (user) {
      const updated = { ...user, role: newRole };
      setUser(updated);
      localStorage.setItem('roadsentinel_user', JSON.stringify(updated));
    }
  };

  return (
    <AuthContext.Provider value={{ user, role, token, login, register, logout, switchRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
