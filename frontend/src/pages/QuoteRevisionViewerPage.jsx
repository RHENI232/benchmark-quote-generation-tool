import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getQuoteRevision } from '../api/quoteApi';
import { useAuth, PERMISSIONS } from '../auth/AuthContext';
import StatusBadge from '../components/common/StatusBadge';
import {
  getActionBadgeClass,
  formatActionLabel,
  formatRevisionDate,
  formatSnapshotMoney,
  formatSnapshotUsd,
  formatSnapshotPercent,
  groupSnapshotLineItems,
  canDisplayCostData,
} from '../utils/revisionFormatters';
import '../styles/wizard.css';

export default function QuoteRevisionViewerPage() {
  const { id, revisionNumber } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const [revision, setRevision] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [errorStatus, setErrorStatus] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  // Validate route parameters upfront: both must be positive integers
  const quoteIdNum = Number(id);
  const revNum = Number(revisionNumber);
  const isQuoteIdValid = Number.isInteger(quoteIdNum) && quoteIdNum > 0 && String(quoteIdNum) === String(id || '').trim();
  const isRevNumValid = Number.isInteger(revNum) && revNum > 0 && String(revNum) === String(revisionNumber || '').trim();

  useEffect(() => {
    if (!isQuoteIdValid || !isRevNumValid) {
      setLoading(false);
      setRevision(null);
      setErrorStatus(400);
      if (!isQuoteIdValid && !isRevNumValid) {
        setError('Invalid route parameters: Quote ID and revision number must both be positive integers.');
      } else if (!isQuoteIdValid) {
        setError("Invalid Quote ID in URL: Must be a positive integer.");
      } else {
        setError("Invalid Revision Number in URL: Must be a positive integer.");
      }
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);
    setErrorStatus(null);

    getQuoteRevision(id, revisionNumber)
      .then((data) => {
        if (isMounted) {
          setRevision(data);
          setError(null);
          setErrorStatus(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Failed to fetch historical revision snapshot:', err);
          setErrorStatus(err.status || 0);
          if (
            err.status === 401 ||
            err.message?.toLowerCase().includes('token has expired') ||
            err.message?.toLowerCase().includes('not authenticated')
          ) {
            setError('Your session has expired or you are not signed in. Please sign in again.');
          } else if (err.status === 403) {
            setError('You do not have permission to view revisions for this quote.');
          } else if (err.status === 404) {
            setError(`Revision #${revisionNumber} does not exist for Quote #${id}.`);
          } else if (err.isNetworkError || err.status === 0) {
            setError('Network error: Unable to connect to the server. Please check your connection.');
          } else if (err.status >= 500) {
            setError('Server error loading historical revision. Please try again later.');
          } else {
            setError(err.message || `Failed to load revision #${revisionNumber}.`);
          }
          setRevision(null);
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    // Cleanup: prevents stale responses from overwriting state when route params change
    return () => {
      isMounted = false;
    };
  }, [id, revisionNumber, isQuoteIdValid, isRevNumValid, retryCount]);

  const handleRetry = () => {
    setRetryCount((prev) => prev + 1);
  };

  // 1. LOADING STATE
  if (loading) {
    return (
      <div className="card" style={{ marginTop: '1.5rem', padding: '3rem 1rem', textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem auto' }}></div>
        <p style={{ color: '#4b5563', fontSize: '1rem', fontWeight: 500 }}>
          Loading historical snapshot for Revision #{revisionNumber}...
        </p>
      </div>
    );
  }

  // 2. ERROR OR MISSING REVISION STATE
  if (error || !revision) {
    const isAuthError = errorStatus === 401 || error?.toLowerCase().includes('session has expired');
    const isForbidden = errorStatus === 403;
    const isNotFound = errorStatus === 404;

    return (
      <div
        className="card border-danger mt-4"
        style={{ padding: '1.5rem', marginTop: '1.5rem', backgroundColor: '#fef2f2', border: '1px solid #fee2e2' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ fontSize: '1.5rem', lineHeight: '1.75rem' }}>
            {isAuthError ? '🔒' : isForbidden ? '🚫' : isNotFound ? '🔍' : '⚠️'}
          </div>
          <div>
            <h3 style={{ margin: 0, color: '#991b1b', fontSize: '1.125rem' }}>
              {isAuthError
                ? 'Authentication Required'
                : isForbidden
                ? 'Access Forbidden'
                : isNotFound
                ? 'Historical Revision Not Found'
                : 'Unable to Load Historical Revision'}
            </h3>
            <p style={{ margin: '0.35rem 0 0 0', color: '#7f1d1d', fontSize: '0.875rem' }}>
              {error || `Revision #${revisionNumber} could not be loaded.`}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1.25rem' }}>
          {isQuoteIdValid && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(`/quotes/${id}`)}
            >
              &larr; Back to Current Quote Details
            </button>
          )}
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={() => navigate('/quotes')}
          >
            Go to Quote List
          </button>
          {isAuthError ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/login', { state: { from: { pathname: `/quotes/${id}/revisions/${revisionNumber}` } } })}
            >
              Sign In
            </button>
          ) : !isNotFound && errorStatus !== 400 && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRetry}
            >
              Retry Loading
            </button>
          )}
        </div>
      </div>
    );
  }

  // Extract snapshot payload safely (authoritative frozen source)
  const snapshot = revision.snapshot_data || {};
  const quote = snapshot.quote || {};
  const financials = snapshot.financials || {};
  const legalEntity = snapshot.legal_entity || {};
  const lineItems = snapshot.line_items || [];

  // Defense-in-depth cost & margin visibility check
  const userHasCostVisibility = hasPermission(PERMISSIONS.COST_VISIBILITY);
  const canShowCost = canDisplayCostData(financials, userHasCostVisibility);

  // Group line items by section, preserving original sort order
  const groupedLineItems = groupSnapshotLineItems(lineItems);
  const sections = Object.keys(groupedLineItems);

  const currencyCode = financials.currency_code || 'USD';
  const requirementData = quote.requirement_data || {};

  return (
    <div className="preview-step-container">
      {/* PAGE HEADER */}
      <div className="preview-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 className="preview-title">Historical Quote Revision</h2>
            <p className="preview-subtitle">
              Viewing read-only historical revision #{revision.revision_number} of Quote {quote.quote_ref_no || `#${id}`}.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/quotes/${id}`)}
          >
            &larr; Back to Current Quote Details
          </button>
        </div>
      </div>

      {/* HISTORICAL IMMUTABLE SNAPSHOT BANNER */}
      <div
        style={{
          backgroundColor: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: '0.5rem',
          padding: '1rem 1.25rem',
          marginBottom: '1.5rem',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div style={{ fontSize: '1.5rem', lineHeight: '1.75rem' }}>📜</div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, color: '#1e40af', fontSize: '1.125rem', fontWeight: 600 }}>
                  Historical Snapshot — Revision #{revision.revision_number} (v{revision.quote_version})
                </h3>
                <span className={`badge ${getActionBadgeClass(revision.action)}`}>
                  {formatActionLabel(revision.action)}
                </span>
              </div>
              <p style={{ margin: '0.35rem 0 0 0', color: '#1e3a8a', fontSize: '0.875rem' }}>
                Captured by <strong>{revision.user_email || `User #${revision.user_id}`}</strong>
                {revision.user_role && ` (${revision.user_role})`} on{' '}
                <strong>{formatRevisionDate(revision.created_at)}</strong>.
              </p>
              {revision.change_reason && (
                <p style={{ margin: '0.25rem 0 0 0', color: '#3b82f6', fontSize: '0.875rem', fontStyle: 'italic' }}>
                  Reason: "{revision.change_reason}"
                </p>
              )}
              <p style={{ margin: '0.35rem 0 0 0', color: '#64748b', fontSize: '0.75rem' }}>
                🔒 This is an immutable past snapshot. All catalog line items, quantities, exchange rates, and financial totals are rendered exactly as stored without recalculation.
              </p>
            </div>
          </div>
          <div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => navigate(`/quotes/${id}`)}
              style={{ fontSize: '0.8125rem' }}
            >
              &larr; Back to Current Quote
            </button>
          </div>
        </div>
      </div>

      {/* QUOTE META HEADER */}
      <div className="quote-meta-header">
        <div className="meta-item">
          <div className="meta-label">Quote #</div>
          <div className="meta-value">{quote.quote_ref_no || `QT-${id}`}</div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Revision / Version</div>
          <div className="meta-value">
            <span className="font-semibold text-gray-900">Rev #{revision.revision_number}</span>
            <span className="badge badge-neutral ms-1" style={{ marginLeft: '0.35rem' }}>
              v{revision.quote_version}
            </span>
          </div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Historical Status</div>
          <div className="meta-value">
            <StatusBadge status={quote.status} />
            {quote.is_urgent && (
              <span className="badge badge-danger ms-2" style={{ marginLeft: '0.5rem' }}>
                URGENT
              </span>
            )}
          </div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Captured Date</div>
          <div className="meta-value">
            {formatRevisionDate(quote.date || quote.created_at || revision.created_at)}
          </div>
        </div>
      </div>

      {/* CUSTOMER & QUOTE INFO PANELS */}
      <div className="info-panels">
        <div className="info-panel">
          <h3 className="section-title">Customer Information</h3>
          <dl className="info-list">
            <dt>Customer</dt>
            <dd>{quote.client_name || '—'}</dd>
            <dt>Attention</dt>
            <dd>{quote.attention || '—'}</dd>
            {quote.description && (
              <>
                <dt>Description</dt>
                <dd className="text-sm">{quote.description}</dd>
              </>
            )}
            {legalEntity.legal_entity_name && (
              <>
                <dt>Legal Entity</dt>
                <dd className="text-sm">
                  {legalEntity.legal_entity_name}
                  {legalEntity.legal_entity_registration_number && (
                    <span className="text-xs text-gray-500 ms-1" style={{ display: 'block' }}>
                      Reg: {legalEntity.legal_entity_registration_number}
                    </span>
                  )}
                </dd>
              </>
            )}
          </dl>
        </div>

        <div className="info-panel">
          <h3 className="section-title">Quotation Snapshot Details</h3>
          <dl className="info-list">
            <dt>Region</dt>
            <dd>{quote.region_name || quote.region_id || '—'}</dd>
            <dt>Solution</dt>
            <dd>{quote.solution_name || quote.solution_id || '—'}</dd>
            <dt>Currency</dt>
            <dd>{currencyCode}</dd>
            <dt>FX Rate</dt>
            <dd>
              <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {financials.fx_rate_to_usd ? parseFloat(financials.fx_rate_to_usd).toFixed(6) : '—'}
              </span>
              {financials.fx_rate_as_of && (
                <span style={{ display: 'block', fontSize: '0.75rem', color: '#6b7280' }}>
                  As of: {financials.fx_rate_as_of}
                </span>
              )}
            </dd>
            <dt>Tax</dt>
            <dd>
              {financials.tax_enabled ? `Yes (${parseFloat(financials.tax_rate_percent || 0).toFixed(1)}%)` : 'No'}
            </dd>
          </dl>
        </div>
      </div>

      {/* REQUIREMENTS SUMMARY (IF PRESENT IN SNAPSHOT) */}
      {requirementData && Object.keys(requirementData).length > 0 && (
        <div className="card mb-4" style={{ marginTop: '1rem', padding: '1rem 1.25rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9375rem', fontWeight: 600, color: '#374151' }}>
            Historical Scope & Requirements
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.8125rem' }}>
            <div>
              <span style={{ color: '#6b7280' }}>Studios:</span>{' '}
              <strong>{requirementData.number_of_studios ?? 1}</strong>
            </div>
            {requirementData.number_of_designers !== undefined && (
              <div>
                <span style={{ color: '#6b7280' }}>Designers:</span>{' '}
                <strong>{requirementData.number_of_designers}</strong>
              </div>
            )}
            {requirementData.news_production !== undefined && (
              <div>
                <span style={{ color: '#6b7280' }}>News Production:</span>{' '}
                <strong>{requirementData.news_production ? 'Yes' : 'No'}</strong>
              </div>
            )}
            {requirementData.journalists !== undefined && requirementData.journalists !== null && (
              <div>
                <span style={{ color: '#6b7280' }}>Journalists:</span>{' '}
                <strong>{requirementData.journalists}</strong>
              </div>
            )}
            {requirementData.mos_redundancy !== undefined && (
              <div>
                <span style={{ color: '#6b7280' }}>MOS Redundancy:</span>{' '}
                <strong>{requirementData.mos_redundancy ? 'Yes' : 'No'}</strong>
              </div>
            )}
            {requirementData.mam !== undefined && (
              <div>
                <span style={{ color: '#6b7280' }}>MAM System:</span>{' '}
                <strong>{requirementData.mam ? 'Yes' : 'No'}</strong>
              </div>
            )}
            {requirementData.three_years_support !== undefined && (
              <div>
                <span style={{ color: '#6b7280' }}>3-Year Support:</span>{' '}
                <strong>{requirementData.three_years_support ? 'Yes' : 'No'}</strong>
              </div>
            )}
          </div>
        </div>
      )}

      {/* BILL OF QUANTITIES (BOQ) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
        <div className="boq-section">
          <div className="boq-header">
            <h3 className="section-title">Bill of Quantities (Snapshot)</h3>
            <p className="form-help">Quoted equipment, software, and services as recorded in Revision #{revision.revision_number}</p>
          </div>
          <div className="table-container">
            <table className="data-table boq-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'center', width: '5%' }}>#</th>
                  <th style={{ width: '15%' }}>Part Number</th>
                  <th style={{ width: '30%' }}>Description</th>
                  <th style={{ textAlign: 'center', width: '5%' }}>Qty</th>
                  {canShowCost && <th className="text-right" style={{ width: '12%' }}>Unit Cost</th>}
                  <th className="text-right" style={{ width: '12%' }}>Unit Sell</th>
                  {canShowCost && <th className="text-right" style={{ width: '8%' }}>Margin</th>}
                  <th className="text-right" style={{ width: '13%' }}>Total Sell</th>
                </tr>
              </thead>
              <tbody>
                {sections.length > 0 ? (
                  sections.map((sectionName) => (
                    <React.Fragment key={sectionName}>
                      {/* Section Header Row */}
                      <tr className="section-row">
                        <td colSpan={canShowCost ? 8 : 6}>
                          {sectionName}
                        </td>
                      </tr>
                      {/* Section Items */}
                      {groupedLineItems[sectionName].map((item, idx) => (
                        <tr key={item.id || `${sectionName}-${idx}`}>
                          <td style={{ textAlign: 'center' }} className="text-gray-500 text-sm">
                            {typeof item.sort_order === 'number' ? item.sort_order + 1 : idx + 1}
                          </td>
                          <td>
                            <div className="font-medium text-gray-900">{item.part_number || 'Custom'}</div>
                            {item.brand && <div className="text-xs text-gray-500">{item.brand}</div>}
                          </td>
                          <td>
                            <div className="text-sm text-gray-900">{item.description}</div>
                          </td>
                          <td style={{ textAlign: 'center' }} className="font-medium">
                            {item.quantity}
                          </td>
                          {canShowCost && (
                            <td className="text-right text-sm text-gray-500">
                              {formatSnapshotUsd(item.unit_cost_price_snapshot)}
                            </td>
                          )}
                          <td className="text-right text-sm">
                            {formatSnapshotUsd(item.unit_sell_price_snapshot)}
                          </td>
                          {canShowCost && (
                            <td className="text-right text-sm">
                              {formatSnapshotPercent(item.margin_percent)}
                            </td>
                          )}
                          <td className="text-right font-medium text-gray-900">
                            {formatSnapshotUsd(item.line_sell_total)}
                          </td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={canShowCost ? 8 : 6} style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                      <div className="text-gray-500">No line items recorded for this historical revision.</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* PRICING SUMMARY */}
        <div className="financial-summary-section" style={{ marginTop: '0' }}>
          <div className="financial-summary-card">
            <h3 className="section-title">Pricing Summary (Historical)</h3>
            <table className="financial-table">
              <tbody>
                {canShowCost && (
                  <tr>
                    <td>Total Cost (USD)</td>
                    <td className="text-right font-medium text-gray-900">
                      {formatSnapshotUsd(financials.subtotal_cost_usd)}
                    </td>
                  </tr>
                )}
                <tr>
                  <td>Subtotal Sell (USD)</td>
                  <td className="text-right font-medium text-gray-900">
                    {formatSnapshotUsd(financials.subtotal_sell_usd)}
                  </td>
                </tr>
                <tr>
                  <td>Tax Amount ({currencyCode})</td>
                  <td className="text-right font-medium text-gray-900">
                    {formatSnapshotMoney(financials.tax_amount, currencyCode)}
                  </td>
                </tr>
                <tr className="total-row">
                  <td className="font-bold text-lg">TOTAL SELL ({currencyCode})</td>
                  <td className="text-right font-bold text-2xl total-value">
                    {formatSnapshotMoney(financials.total_sell_local, currencyCode)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* FOOTER ACTION BAR */}
      <div className="preview-actions" style={{ marginTop: '2rem' }}>
        <div className="action-left" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={() => navigate(`/quotes/${id}`)}
          >
            &larr; Back to Current Quote Details
          </button>
        </div>
        <div className="action-right" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.8125rem', color: '#6b7280', fontStyle: 'italic' }}>
            Historical revisions are immutable and read-only.
          </span>
        </div>
      </div>
    </div>
  );
}
