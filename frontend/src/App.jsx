import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, ROLES } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import AcceptInvitePage from './pages/AcceptInvitePage';
import DashboardPage from './pages/DashboardPage';
import QuoteListPage from './pages/QuoteListPage';
import QuoteWizardPage from './pages/QuoteWizardPage';
import QuoteDetailPage from './pages/QuoteDetailPage';
import ApprovalQueuePage from './pages/ApprovalQueuePage';
import UserAdminPage from './pages/UserAdminPage';
import './styles/global.css';
import './styles/components.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/invite/accept" element={<AcceptInvitePage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/quotes" element={<QuoteListPage />} />
            <Route path="/quotes/new" element={<QuoteWizardPage />} />
            <Route path="/quotes/:id/edit" element={<QuoteWizardPage />} />
            <Route path="/quotes/:id" element={<QuoteDetailPage />} />
          </Route>
          <Route element={<ProtectedRoute requiredPermission="finance_tax_admin" />}>
            <Route path="/approval-queue" element={<ApprovalQueuePage />} />
          </Route>
          <Route element={<ProtectedRoute roles={[ROLES.ADMIN]} />}>
            <Route path="/users" element={<UserAdminPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
