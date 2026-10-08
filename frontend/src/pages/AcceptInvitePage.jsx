import React, { useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { acceptInvite } from '../api/authApi';
import '../styles/login.css';

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);


  if (!token) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="brand-logo">Benchmark</div>
            <h1 className="login-title">Invalid Invitation</h1>
            <p className="login-subtitle">No invitation token was found in the URL.</p>
          </div>
          <div style={{ textAlign: 'center', marginTop: '1rem' }}>
            <Link to="/login" className="btn btn-secondary">Return to Login</Link>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (!password || !confirmPassword) {
      setError('Please fill out both password fields.');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    
    setIsSubmitting(true);

    try {
      await acceptInvite(token, password);
      setSuccess(true);
    } catch (err) {
      setError(err.message || 'Failed to accept invitation. The token may be expired or invalid.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <div className="brand-logo">Benchmark</div>
            <h1 className="login-title">Account Activated</h1>
            <p className="login-subtitle">Your password has been set successfully.</p>
          </div>
          <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
            <Link to="/login" className="btn btn-primary login-btn">Go to Login</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="brand-logo">Benchmark</div>
          <h1 className="login-title">Accept Invitation</h1>
          <p className="login-subtitle">Set your password to activate your account</p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="password" className="form-label">New Password</label>
            <input
              id="password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isSubmitting}
              autoComplete="new-password"
            />
          </div>
          <div className="form-group">
            <label htmlFor="confirmPassword" className="form-label">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              className="form-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              disabled={isSubmitting}
              autoComplete="new-password"
            />
          </div>
          <button type="submit" className="btn btn-primary login-btn" disabled={isSubmitting}>
            {isSubmitting ? 'Activating...' : 'Activate Account'}
          </button>
        </form>
      </div>
    </div>
  );
}

