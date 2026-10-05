import React from 'react';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import '../../styles/layout.css';

export default function AppLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-title">
          <span className="brand-name">Benchmark</span>
          <span className="app-name">Presales Tool</span>
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
