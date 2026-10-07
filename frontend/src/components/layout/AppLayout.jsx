import React from 'react';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import { useAuth, PERMISSIONS } from '../../auth/AuthContext';
import '../../styles/layout.css';

export default function AppLayout({ children }) {
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-title">
          <a href="https://benchmarkbroadcast.com/" target="_blank" rel="noopener noreferrer" className="brand-logo-link">
            <img src="/assets/logo.webp" alt="Benchmark Broadcast Systems" className="brand-logo" />
          </a>
        </div>
        <div className="app-user-controls">
          <div className="user-info">
            <span className="user-email">{user?.email}</span>
            <span className="user-role">{user?.role_tier}</span>
          </div>
          <button onClick={handleLogout} className="btn-logout">Logout</button>
        </div>
      </header>
      <div className="app-body">
        <aside className="app-sidebar">
          <nav className="app-nav">
            <ul>
              <li>
                <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
                  Dashboard
                </NavLink>
              </li>
              <li>
                <NavLink to="/quotes" className={({ isActive }) => (isActive ? 'active' : '')}>
                  Quotes
                </NavLink>
              </li>
              {hasPermission(PERMISSIONS.SUPER_ADMIN) && (
                <li>
                  <NavLink to="/users" className={({ isActive }) => (isActive ? 'active' : '')}>
                    Users
                  </NavLink>
                </li>
              )}
            </ul>
          </nav>
        </aside>
        <main className="app-content">
          {children}
        </main>
      </div>
    </div>
  );
}
