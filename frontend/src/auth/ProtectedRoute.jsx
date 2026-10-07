import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';
import AppLayout from '../components/layout/AppLayout';

export default function ProtectedRoute({ roles }) {
  const { user, isLoading, hasRole } = useAuth();

  if (isLoading) {
    return <div className="loading-container">Loading application...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (roles && roles.length > 0 && !hasRole(...roles)) {
    return (
      <AppLayout>
        <div className="container mt-5">
          <div className="alert alert-danger">
            <h4>Access Denied</h4>
            <p>You do not have permission to view this page.</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
}
