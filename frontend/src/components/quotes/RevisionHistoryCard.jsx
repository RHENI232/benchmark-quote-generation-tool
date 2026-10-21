import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getQuoteRevisions } from '../../api/quoteApi';
import {
  getActionBadgeClass,
  formatActionLabel,
  formatRevisionDate,
} from '../../utils/revisionFormatters';

export default function RevisionHistoryCard({
  quoteId,
  currentQuoteVersion,
  refreshTrigger,
  onViewSnapshot,
}) {
  const navigate = useNavigate();
  const [revisions, setRevisions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [order, setOrder] = useState('desc'); // Default to newest first

  const fetchRevisions = useCallback(async () => {
    if (!quoteId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getQuoteRevisions(quoteId, { order });
      setRevisions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch quote revisions:', err);
      if (
        err.status === 401 ||
        err.message?.toLowerCase().includes('token has expired') ||
        err.message?.toLowerCase().includes('not authenticated')
      ) {
        setError('Your session has expired or you are not signed in. Please sign in again.');
      } else if (err.status === 403) {
        setError('You do not have permission to view revisions for this quote.');
      } else if (err.status === 404) {
        setError('Quote not found.');
      } else if (err.status === 500) {
        setError('Server error loading revisions. Please try again later.');
      } else {
        setError(err.message || 'Failed to load revision history.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [quoteId, order]);

  useEffect(() => {
    fetchRevisions();
  }, [fetchRevisions, refreshTrigger]);

  const handleViewSnapshot = (revisionNumber) => {
    if (onViewSnapshot) {
      onViewSnapshot(revisionNumber);
    } else {
      navigate(`/quotes/${quoteId}/revisions/${revisionNumber}`);
    }
  };

  return (
    <div className="card mb-4" style={{ marginTop: '1.5rem' }}>
      {/* CARD HEADER */}
      <div
        className="card-header"
        style={{
          padding: '0.75rem 1.25rem',
          backgroundColor: '#f9fafb',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: '#374151' }}>
            Quote Revision History
          </h3>
          {!isLoading && !error && revisions.length > 0 && (
            <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
              {revisions.length} {revisions.length === 1 ? 'revision' : 'revisions'}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.75rem', color: '#6b7280', margin: 0 }}>
            Sort:
          </label>
          <select
            value={order}
            onChange={(e) => setOrder(e.target.value)}
            disabled={isLoading}
            style={{
              fontSize: '0.75rem',
              padding: '0.25rem 0.5rem',
              borderRadius: '0.25rem',
              border: '1px solid #d1d5db',
              backgroundColor: '#ffffff',
              color: '#374151',
            }}
            aria-label="Sort revision order"
          >
            <option value="desc">Newest First</option>
            <option value="asc">Oldest First</option>
          </select>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={fetchRevisions}
            disabled={isLoading}
            title="Refresh revision history"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
          {revisions.length >= 2 && (
            <button
              type="button"
              className="btn btn-sm btn-outline-primary"
              onClick={() => navigate(`/quotes/${quoteId}/revisions/compare`)}
              title="Compare quote revisions"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            >
              Compare Revisions
            </button>
          )}
        </div>
      </div>

      {/* ERROR STATE WITH RETRY OR SIGN IN */}
      {error && (
        <div
          style={{
            padding: '1rem 1.25rem',
            backgroundColor: '#fef2f2',
            borderBottom: '1px solid #fee2e2',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '0.75rem',
          }}
        >
          <div style={{ color: '#991b1b', fontSize: '0.875rem' }}>
            <strong>Unable to load revisions:</strong> {error}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {(error.includes('session has expired') || error.includes('sign in')) && (
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={() => navigate('/login', { state: { from: { pathname: `/quotes/${quoteId}` } } })}
              >
                Sign In
              </button>
            )}
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={fetchRevisions}
              disabled={isLoading}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* LOADING STATE */}
      {isLoading ? (
        <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#6b7280' }}>
          <div className="spinner" style={{ margin: '0 auto 0.5rem auto' }}></div>
          <span style={{ fontSize: '0.875rem' }}>Loading quote revision history...</span>
        </div>
      ) : !error && revisions.length === 0 ? (
        /* EMPTY STATE */
        <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#6b7280' }}>
          <div style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>📋</div>
          <p style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 500, color: '#374151' }}>
            No historical revisions captured for this quote yet.
          </p>
          <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.8125rem', color: '#9ca3af' }}>
            Immutable revisions are automatically captured whenever quotes are created, edited, recalculated, submitted, approved, or refreshed.
          </p>
        </div>
      ) : (
        /* REVISION TABLE */
        !error && (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '8%', textAlign: 'center' }}>Rev #</th>
                  <th style={{ width: '8%', textAlign: 'center' }}>Version</th>
                  <th style={{ width: '16%' }}>Action</th>
                  <th style={{ width: '22%' }}>Captured By</th>
                  <th style={{ width: '18%' }}>Timestamp</th>
                  <th style={{ width: '18%' }}>Change Reason</th>
                  <th style={{ width: '15%', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {revisions.map((rev) => {
                  const isCurrent = currentQuoteVersion !== undefined && rev.quote_version === currentQuoteVersion;
                  return (
                    <tr key={rev.id || `${rev.quote_id}-${rev.revision_number}`}>
                      <td style={{ textAlign: 'center', fontWeight: 600 }} className="text-gray-900">
                        #{rev.revision_number}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                          v{rev.quote_version}
                        </span>
                        {isCurrent && (
                          <span
                            className="badge badge-success"
                            style={{ fontSize: '0.65rem', marginLeft: '0.25rem' }}
                            title="Matches the current version of the quote"
                          >
                            current
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${getActionBadgeClass(rev.action)}`}>
                          {formatActionLabel(rev.action)}
                        </span>
                      </td>
                      <td className="text-sm font-medium text-gray-900">
                        {rev.user_email || `User #${rev.user_id}`}
                        {rev.user_role && (
                          <span className="text-xs text-gray-500 ms-1" style={{ display: 'block', fontWeight: 400 }}>
                            {rev.user_role}
                          </span>
                        )}
                      </td>
                      <td className="text-sm text-gray-500">
                        {formatRevisionDate(rev.created_at)}
                      </td>
                      <td className="text-sm text-gray-800" style={{ whiteSpace: 'pre-wrap' }}>
                        {rev.change_reason ? (
                          rev.change_reason
                        ) : (
                          <span className="text-gray-400 italic">—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => handleViewSnapshot(rev.revision_number)}
                          title={`View historical snapshot for Revision ${rev.revision_number}`}
                          style={{
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            cursor: 'pointer',
                            fontSize: '0.8125rem',
                            color: 'var(--color-brand-600, #1c3d73)',
                            textDecoration: 'underline',
                            marginRight: '0.75rem',
                          }}
                        >
                          View Snapshot
                        </button>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => navigate(`/quotes/${quoteId}/revisions/compare?from=${rev.revision_number}`)}
                          title={`Compare Revision ${rev.revision_number} with another revision`}
                          style={{
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            cursor: 'pointer',
                            fontSize: '0.8125rem',
                            color: '#475569',
                            textDecoration: 'underline',
                          }}
                        >
                          Compare
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
