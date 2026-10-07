import React, { createContext, useState, useEffect, useContext } from 'react';
import { getCurrentUser } from '../api/userApi';
import { login as apiLogin } from '../api/authApi';

export const ROLES = {
  ADMIN: 'Admin',
  MANAGEMENT: 'Management',
  CATALOG_ENTRY: 'Catalog Entry',
  SALES: 'Sales',
};

export const PERMISSIONS = {
  SALES_USER: 'sales_user',
  CATALOG_EDIT: 'catalog_edit',
  COST_VISIBILITY: 'cost_visibility',
  FINANCE_TAX_ADMIN: 'finance_tax_admin',
  SOLUTION_ADMIN: 'solution_admin',
  SUPER_ADMIN: 'super_admin',
};

const ROLE_PERMISSIONS = {
  [ROLES.SALES]: [PERMISSIONS.SALES_USER],
  [ROLES.CATALOG_ENTRY]: [PERMISSIONS.SALES_USER, PERMISSIONS.CATALOG_EDIT],
  [ROLES.MANAGEMENT]: [
    PERMISSIONS.SALES_USER,
    PERMISSIONS.CATALOG_EDIT,
    PERMISSIONS.COST_VISIBILITY,
    PERMISSIONS.FINANCE_TAX_ADMIN
  ],
  [ROLES.ADMIN]: [
    PERMISSIONS.SALES_USER,
    PERMISSIONS.CATALOG_EDIT,
    PERMISSIONS.COST_VISIBILITY,
    PERMISSIONS.FINANCE_TAX_ADMIN,
    PERMISSIONS.SOLUTION_ADMIN,
    PERMISSIONS.SUPER_ADMIN
  ],
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setIsLoading(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error('Auth check failed:', error);
      localStorage.removeItem('access_token');
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();

    // Listen for unauthorized events from the API client
    const handleUnauthorized = () => {
      setUser(null);
    };
    window.addEventListener('unauthorized', handleUnauthorized);
    return () => window.removeEventListener('unauthorized', handleUnauthorized);
  }, []);

  const login = async (email, password) => {
    const response = await apiLogin(email, password);
    localStorage.setItem('access_token', response.access_token);
    await checkAuth(); // Fetch user data
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
  };

  const isRole = (role) => {
    return user?.role_tier === role;
  };

  const hasRole = (...roles) => {
    return !!(user && roles.includes(user.role_tier));
  };

  const hasPermission = (permission) => {
    if (!user || !user.role_tier) return false;
    const permissions = ROLE_PERMISSIONS[user.role_tier] || [];
    return permissions.includes(permission);
  };

  const value = {
    user,
    isLoading,
    login,
    logout,
    isRole,
    hasRole,
    hasPermission
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
