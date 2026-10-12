import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getQuote, submitQuote, approveQuote, requestChangesQuote, overrideApproveQuote } from '../api/quoteApi';
import { regionApi } from '../api/regionApi';
import { solutionApi } from '../api/solutionApi';
import { useAuth, PERMISSIONS } from '../auth/AuthContext';
import '../styles/wizard.css';

export default function QuoteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [quote, setQuote] = useState(null);
  const [regions, setRegions] = useState([]);
  const [solutions, setSolutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Workflow state
  const [isSubmittingWorkflow, setIsSubmittingWorkflow] = useState(false);
  const [workflowAction, setWorkflowAction] = useState(null); // 'request_changes' | 'override_approve'
  const [workflowComment, setWorkflowComment] = useState('');
  const [conflictError, setConflictError] = useState('');

  useEffect(() => {
    let isMounted = true;
    const fetchQuoteDetails = async () => {
      try {
        setLoading(true);
        setError(null);
        const [quoteData, regionsData, solutionsData] = await Promise.all([
          getQuote(id),
          regionApi.getRegions().catch(e => { console.warn("Failed to get regions:", e); return []; }),
          solutionApi.getSolutions().catch(e => { console.warn("Failed to get solutions:", e); return []; })
        ]);
        if (isMounted) { setQuote(quoteData); setRegions(regionsData); setSolutions(solutionsData); setLoading(false); }
      } catch (err) {
        if (isMounted) { console.error('Failed to fetch quote details:', err); setError(err.message || 'Failed to load quote details.'); setLoading(false); }
      }
    };
    if (id) { fetchQuoteDetails(); }
    return () => { isMounted = false; };
  }, [id]);

  const handleWorkflowAction = async (actionType) => {
    setConflictError('');
    setIsSubmittingWorkflow(true);
    try {
      if (actionType === 'submit') {
        await submitQuote(id, { expected_version: quote.version });
      } else if (actionType === 'approve') {
        await approveQuote(id, { expected_version: quote.version, comment: '' });
      } else if (actionType === 'request_changes' || actionType === 'override_approve') {
        if (!workflowComment.trim()) {
          setConflictError('A comment is required for this action.');
          setIsSubmittingWorkflow(false);
          return;
        }
        const payload = { expected_version: quote.version, comment: workflowComment.trim() };
        if (actionType === 'request_changes') {
          await requestChangesQuote(id, payload);
        } else {
          await overrideApproveQuote(id, payload);
        }
        setWorkflowAction(null);
        setWorkflowComment('');
      }
      // Refresh the quote
      const updatedQuote = await getQuote(id);
      setQuote(updatedQuote);
    } catch (err) {
      if (err.status === 409) {
        setConflictError('The quote was updated by another user. Please refresh the page.');
      } else {
        setConflictError(err.message || 'Workflow action failed.');
      }
    } finally {
      setIsSubmittingWorkflow(false);
    }
  };

  if (loading) {
    return (
      <div className="card">
        <div className="card-body text-center py-5">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p className="mt-3">Loading quote details...</p>
        </div>
      </div>
    );
  }

  if (error || !quote) {
    return (
      <div className="card border-danger mt-4">
        <div className="card-header bg-danger text-white">Error</div>
        <div className="card-body">
          <p className="text-danger">{error || 'Quote not found.'}</p>
          <div className="mt-4">
            <button className="btn btn-secondary" onClick={() => navigate('/quotes')}>
              Back to Quotes
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Lookups
  const getRegionName = (regionId) => {
    if (!regions.length) return regionId;
    const r = regions.find(x => x.id === parseInt(regionId, 10));
    return r ? r.country_name : regionId;
  };

  const getSolutionName = (solutionId) => {
    if (!solutions.length) return solutionId;
    const s = solutions.find(x => x.id === parseInt(solutionId, 10));
    return s ? s.name : solutionId;
  };

  const formatMoney = (amount) => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: quote.currency_code || 'USD'
    }).format(num);
  };

  const formatUsd = (amount) => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(num);
  };

  const formatPercent = (amount) => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 2
    }).format(num / 100);
  };

  const hasCostData = quote.subtotal_cost_usd !== null && quote.subtotal_cost_usd !== undefined;

  // Group line items by section
  const groupedLineItems = {};
  if (quote.line_items) {
    quote.line_items.forEach(item => {
      const sec = item.section || 'General';
      if (!groupedLineItems[sec]) groupedLineItems[sec] = [];
      groupedLineItems[sec].push(item);
    });
  }
  const sections = Object.keys(groupedLineItems);

  return (
    <div className="preview-step-container">
      {/* PROFESSIONAL HEADER */}
      <div className="preview-header">
        <h2 className="preview-title">Quote Details</h2>
        <p className="preview-subtitle">Read-only view of the generated quote.</p>
      </div>

      {/* QUOTE META HEADER */}
      <div className="quote-meta-header">
        <div className="meta-item">
          <div className="meta-label">Quote #</div>
          <div className="meta-value">{quote.quote_ref_no || `QT-${quote.id}`}</div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Status</div>
          <div className="meta-value">
            <span className={`badge ${quote.status === 'APPROVED' ? 'badge-success' : (quote.status === 'DRAFT' || quote.status === 'PENDING_APPROVAL' || quote.status === 'CHANGES_REQUESTED' ? 'badge-warning' : 'badge-neutral')}`}>
              {quote.status ? quote.status.toUpperCase().replace('_', ' ') : 'UNKNOWN'}
            </span>
            {quote.is_urgent && (
              <span className="badge badge-danger ms-2" style={{ marginLeft: '0.5rem' }}>URGENT</span>
            )}
          </div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Date</div>
          <div className="meta-value">{quote.date ? new Date(quote.date).toLocaleDateString() : (quote.created_at ? new Date(quote.created_at).toLocaleDateString() : new Date().toLocaleDateString())}</div>
        </div>
      </div>

      {/* CUSTOMER & QUOTE INFO */}
      <div className="info-panels">
        <div className="info-panel">
          <h3 className="section-title">Customer Information</h3>
          <dl className="info-list">
            <dt>Customer</dt>
            <dd>{quote.client_name}</dd>
            {quote.attention && (
              <>
                <dt>Attention</dt>
                <dd>{quote.attention}</dd>
              </>
            )}
            {quote.description && (
              <>
                <dt>Description</dt>
                <dd className="text-sm">{quote.description}</dd>
              </>
            )}
          </dl>
        </div>
        <div className="info-panel">
          <h3 className="section-title">Quote Details</h3>
          <dl className="info-list">
            <dt>Region</dt>
            <dd>{getRegionName(quote.region_id)}</dd>
            <dt>Solution</dt>
            <dd>{getSolutionName(quote.solution_id)}</dd>
            <dt>Currency</dt>
            <dd>{quote.currency_code}</dd>
            <dt>FX Rate</dt>
            <dd>{quote.fx_rate_to_usd ? parseFloat(quote.fx_rate_to_usd).toFixed(4) : '-'}</dd>
            <dt>Tax</dt>
            <dd>{quote.tax_amount > 0 ? `Yes` : 'No'}</dd>
          </dl>
        </div>
      </div>

      {/* WRAPPER TO REDUCE BOQ AND SUMMARY GAP */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {/* LINE ITEMS */}
      <div className="boq-section">
        <div className="boq-header">
          <h3 className="section-title">Bill of Quantities</h3>
          <p className="form-help">Quoted equipment, software and services</p>
        </div>
        <div className="table-container">
          <table className="data-table boq-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'center', width: '5%' }}>#</th>
                <th style={{ width: '15%' }}>Part Number</th>
                <th style={{ width: '30%' }}>Description</th>
                <th style={{ textAlign: 'center', width: '5%' }}>Qty</th>
                {hasCostData && <th className="text-right" style={{ width: '12%' }}>Unit Cost</th>}
                <th className="text-right" style={{ width: '12%' }}>Unit Sell</th>
                {hasCostData && <th className="text-right" style={{ width: '8%' }}>Margin</th>}
                <th className="text-right" style={{ width: '13%' }}>Total Sell</th>
              </tr>
            </thead>
            <tbody>
              {sections.length > 0 ? (
                sections.map((sectionName) => (
                  <React.Fragment key={sectionName}>
                    {/* Section Header Row */}
                    <tr className="section-row">
                      <td colSpan={hasCostData ? 8 : 6}>
                        {sectionName}
                      </td>
                    </tr>
                    {/* Section Items */}
                    {groupedLineItems[sectionName].map((item, idx) => (
                      <tr key={`${sectionName}-${idx}`}>
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
                        <td style={{ textAlign: 'center' }} className="font-medium">{item.quantity}</td>
                        {hasCostData && <td className="text-right text-sm text-gray-500">{formatUsd(item.unit_cost_price_snapshot)}</td>}
                        <td className="text-right text-sm">{formatUsd(item.unit_sell_price_snapshot)}</td>
                        {hasCostData && <td className="text-right text-sm">{formatPercent(item.margin_percent)}</td>}
                        <td className="text-right font-medium text-gray-900">{formatUsd(item.line_sell_total)}</td>
                      </tr>
                    ))}
                  </React.Fragment>
                ))
              ) : (
                <tr>
                  <td colSpan={hasCostData ? 8 : 6} style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                    <div className="text-gray-500">No line items for this quote</div>
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
          <h3 className="section-title">Pricing Summary</h3>
          <table className="financial-table">
            <tbody>
              {hasCostData && (
                <tr>
                  <td>Total Cost (USD)</td>
                  <td className="text-right font-medium text-gray-900">{formatUsd(quote.subtotal_cost_usd)}</td>
                </tr>
              )}
              <tr>
                <td>Subtotal Sell (USD)</td>
                <td className="text-right font-medium text-gray-900">{formatUsd(quote.subtotal_sell_usd)}</td>
              </tr>
              <tr>
                <td>Tax Amount ({quote.currency_code})</td>
                <td className="text-right font-medium text-gray-900">{formatMoney(quote.tax_amount)}</td>
              </tr>
              <tr className="total-row">
                <td className="font-bold text-lg">TOTAL SELL ({quote.currency_code})</td>
                <td className="text-right font-bold text-2xl total-value">{formatMoney(quote.total_sell_local)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </div>

      {/* WORKFLOW MESSAGES */}
      {conflictError && (
        <div className="alert alert-danger mt-3 mb-3">
          {conflictError}
          {conflictError.includes('refresh') && (
            <button className="btn btn-sm btn-outline-danger ms-3" onClick={() => window.location.reload()}>
              Refresh Page
            </button>
          )}
        </div>
      )}

      {/* BUTTON AREA */}
      <div className="preview-actions">
        <div className="action-left">
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={() => navigate('/quotes')}
            disabled={isSubmittingWorkflow}
          >
            &larr; Back to Quotes
          </button>
        </div>
        <div className="action-right" style={{ display: 'flex', gap: '0.5rem' }}>
          {quote.status === 'draft' && (
            <>
              <button
                type="button"
                className="btn btn-secondary btn-lg"
                onClick={() => navigate(`/quotes/${quote.id}/edit`)}
                disabled={isSubmittingWorkflow}
              >
                Edit Draft
              </button>
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={() => handleWorkflowAction('submit')}
                disabled={isSubmittingWorkflow}
              >
                Submit for Approval
              </button>
            </>
          )}
          {quote.status === 'pending_approval' && hasPermission(PERMISSIONS.FINANCE_TAX_ADMIN) && (
            <>
              <button
                type="button"
                className="btn btn-danger btn-lg"
                onClick={() => setWorkflowAction('request_changes')}
                disabled={isSubmittingWorkflow}
              >
                Request Changes
              </button>
              <button
                type="button"
                className="btn btn-success btn-lg"
                onClick={() => handleWorkflowAction('approve')}
                disabled={isSubmittingWorkflow}
              >
                Approve
              </button>
            </>
          )}
          {quote.status === 'pending_approval' && hasPermission(PERMISSIONS.SUPER_ADMIN) && (
            <button
              type="button"
              className="btn btn-warning btn-lg"
              onClick={() => setWorkflowAction('override_approve')}
              disabled={isSubmittingWorkflow}
            >
              Override Approve
            </button>
          )}
        </div>
      </div>

      {/* WORKFLOW MODAL */}
      {workflowAction && (
        <div className="modal-backdrop" style={{ display: 'block', backgroundColor: 'rgba(0,0,0,0.5)', position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 1040 }}>
          <div className="modal" style={{ display: 'block', zIndex: 1050 }} tabIndex="-1">
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    {workflowAction === 'request_changes' ? 'Request Changes' : 'Override Approve'}
                  </h5>
                  <button type="button" className="btn-close" onClick={() => { setWorkflowAction(null); setWorkflowComment(''); }}></button>
                </div>
                <div className="modal-body">
                  <div className="form-group">
                    <label>Reason / Comment (Required)</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={workflowComment}
                      onChange={(e) => setWorkflowComment(e.target.value)}
                      placeholder="Please enter a required reason..."
                    ></textarea>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => { setWorkflowAction(null); setWorkflowComment(''); }} disabled={isSubmittingWorkflow}>Cancel</button>
                  <button type="button" className={`btn ${workflowAction === 'request_changes' ? 'btn-danger' : 'btn-warning'}`} onClick={() => handleWorkflowAction(workflowAction)} disabled={!workflowComment.trim() || isSubmittingWorkflow}>
                    {isSubmittingWorkflow ? 'Submitting...' : 'Confirm'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
