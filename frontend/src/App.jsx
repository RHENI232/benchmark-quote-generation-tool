import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import QuoteListPage from './pages/QuoteListPage';
import QuoteWizardPage from './pages/QuoteWizardPage';
import QuoteDetailPage from './pages/QuoteDetailPage';
import './styles/global.css';
import './styles/components.css';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute />}>
            <Route index element={<DashboardPage />} />
            <Route path="quotes" element={<QuoteListPage />} />
            <Route path="quotes/new" element={<QuoteWizardPage />} />
            <Route path="quotes/:id/edit" element={<QuoteWizardPage />} />
            <Route path="quotes/:id" element={<QuoteDetailPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
