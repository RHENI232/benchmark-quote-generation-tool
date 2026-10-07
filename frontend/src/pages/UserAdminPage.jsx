import React, { useState, useEffect } from 'react';
import PageHeader from '../components/common/PageHeader';
import {
  getUsers,
  inviteUser,
  updateUserRole,
  updateUserStatus,
  deleteUser
} from '../api/userApi';
import { ROLES, useAuth } from '../auth/AuthContext';

export default function UserAdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState(ROLES.SALES);
  const [isInviting, setIsInviting] = useState(false);
  const [inviteToken, setInviteToken] = useState(null);
  const [inviteError, setInviteError] = useState(null);

  const [actionError, setActionError] = useState(null);

  const fetchUsers = async () => {
    try {
      setError(null);
      const data = await getUsers();
      setUsers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleInvite = async (e) => {
    e.preventDefault();
    setIsInviting(true);
    setInviteError(null);
    setInviteToken(null);
    try {
      const response = await inviteUser(inviteEmail, inviteRole);
      setInviteEmail('');
      setInviteRole(ROLES.SALES);
      if (response.token) {
        setInviteToken(response.token);
      }
      await fetchUsers();
    } catch (err) {
      setInviteError(err.message);
    } finally {
      setIsInviting(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    setActionError(null);
    try {
      await updateUserRole(userId, newRole);
      await fetchUsers();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleStatusChange = async (userId, newStatus) => {
    setActionError(null);
    try {
      await updateUserStatus(userId, newStatus);
      await fetchUsers();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleDelete = async (userId) => {
    if (!window.confirm("Are you sure you want to delete this user?")) {
      return;
    }
    setActionError(null);
    try {
      await deleteUser(userId);
      await fetchUsers();
    } catch (err) {
      setActionError(err.message);
    }
  };

  if (isLoading) {
    return <div className="loading-container">Loading users...</div>;
  }

  return (
    <div className="page-container">
      <PageHeader title="User Administration" />

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {actionError && (
        <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
          {actionError}
        </div>
      )}

      <div style={{ marginBottom: '2rem', padding: '1.5rem', backgroundColor: '#f8fafc', borderRadius: '0.5rem', border: '1px solid #e2e8f0' }}>
        <h3 style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1.1rem' }}>Invite New User</h3>
        
        {inviteError && (
          <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
            {inviteError}
          </div>
        )}

        {inviteToken && (
          <div className="alert alert-success" style={{ marginBottom: '1rem', backgroundColor: '#dcfce3', color: '#166534', border: '1px solid #bbf7d0', padding: '1rem', borderRadius: '0.375rem' }}>
            <strong>Invitation created successfully!</strong>
            <p style={{ margin: '0.5rem 0 0 0' }}>Development Token (Do not share): <code style={{ backgroundColor: 'rgba(255,255,255,0.7)', padding: '0.2rem 0.4rem', borderRadius: '0.25rem' }}>{inviteToken}</code></p>
          </div>
        )}

        <form onSubmit={handleInvite} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 250px' }}>
            <label className="form-label" htmlFor="invite-email">Email Address</label>
            <input
              id="invite-email"
              type="email"
              className="form-control"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              required
              disabled={isInviting}
              style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
            />
          </div>
          
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 200px' }}>
            <label className="form-label" htmlFor="invite-role">Role</label>
            <select
              id="invite-role"
              className="form-control"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              disabled={isInviting}
              style={{ width: '100%', padding: '0.5rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
            >
              <option value={ROLES.SALES}>Sales</option>
              <option value={ROLES.CATALOG_ENTRY}>Catalog Entry</option>
              <option value={ROLES.MANAGEMENT}>Management</option>
              <option value={ROLES.ADMIN}>Admin</option>
            </select>
          </div>
          
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={isInviting || !inviteEmail}
          >
            {isInviting ? 'Inviting...' : 'Invite User'}
          </button>
        </form>
      </div>

      <div className="table-container">
        {users.length === 0 ? (
          <p>No users found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Account Type</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isCurrentUser = currentUser?.id === u.id;
                return (
                  <tr key={u.id}>
                    <td>
                      {u.email}
                      {isCurrentUser && <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#64748b' }}>(You)</span>}
                    </td>
                    <td>
                      <select
                        value={u.role_tier}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        style={{ padding: '0.25rem', border: '1px solid #cbd5e1', borderRadius: '0.25rem' }}
                      >
                        <option value={ROLES.SALES}>Sales</option>
                        <option value={ROLES.CATALOG_ENTRY}>Catalog Entry</option>
                        <option value={ROLES.MANAGEMENT}>Management</option>
                        <option value={ROLES.ADMIN}>Admin</option>
                      </select>
                    </td>
                    <td>
                      <span className={`badge ${u.enabled ? 'badge-success' : 'badge-neutral'}`}>
                        {u.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </td>
                    <td>{u.account_type}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {u.enabled ? (
                          <button
                            className="btn btn-secondary"
                            onClick={() => handleStatusChange(u.id, false)}
                            disabled={isCurrentUser}
                            title={isCurrentUser ? "You cannot disable yourself" : "Disable User"}
                          >
                            Disable
                          </button>
                        ) : (
                          <button
                            className="btn btn-primary"
                            onClick={() => handleStatusChange(u.id, true)}
                          >
                            Enable
                          </button>
                        )}
                        <button
                          className="btn btn-danger"
                          onClick={() => handleDelete(u.id)}
                          disabled={isCurrentUser}
                          title={isCurrentUser ? "You cannot delete yourself" : "Delete User"}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

