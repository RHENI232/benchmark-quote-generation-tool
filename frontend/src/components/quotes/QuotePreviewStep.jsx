import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { previewQuote, createQuote, saveQuoteStatus, updateQuote } from '../../api/quoteApi';
import { regionApi } from '../../api/regionApi';
import { solutionApi } from '../../api/solutionApi';

export default function QuotePreviewStep({ draftQuote, onBack }) {
  const [previewData, setPreviewData] = useState(null);
  const [regions, setRegions] = useState([]);
  const [solutions, setSolutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveAction, setSaveAction] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const navigate = useNavigate();

  const handleSaveDraft = async () => {
    try {
      setIsSaving(true);
      setSaveAction('draft');
      setError(null);

      const payload = {
        client_name: draftQuote.client_name,
        attention: draftQuote.attention || undefined,
        description: draftQuote.description || undefined,
        region_id: draftQuote.region_id === '' ? undefined : Number(draftQuote.region_id),
        solution_id: draftQuote.solution_id === '' ? undefined : Number(draftQuote.solution_id),
        requirement_data: {
          ...draftQuote.requirement_data,
          studios: Array.isArray(draftQuote.studios) ? draftQuote.studios : []
        }
      };

      if (draftQuote.id) {
        payload.expected_version = draftQuote.version;
        await updateQuote(draftQuote.id, payload);
      } else {
        await createQuote(payload);
      }

      localStorage.removeItem('quote_wizard_backup');
      navigate('/quotes');
    } catch (err) {
      console.error("Save draft failed:", err);
      setError(err.message || 'Failed to save quote as draft. Please try again.');
      setIsSaving(false);
      setSaveAction(null);
    }
  };

  const handleSaveFinal = async () => {
    let createdQuoteId = null;
    let createdQuoteVersion = null;
    let quoteRef = null;
    try {
      setIsSaving(true);
      setSaveAction('final');
      setError(null);

      const payload = {
        client_name: draftQuote.client_name,
        attention: draftQuote.attention || undefined,
        description: draftQuote.description || undefined,
        region_id: draftQuote.region_id === '' ? undefined : Number(draftQuote.region_id),
        solution_id: draftQuote.solution_id === '' ? undefined : Number(draftQuote.solution_id),
        requirement_data: {
          ...draftQuote.requirement_data,
          studios: Array.isArray(draftQuote.studios) ? draftQuote.studios : []
        }
      };

      if (draftQuote.id) {
        payload.expected_version = draftQuote.version;
        const updated = await updateQuote(draftQuote.id, payload);
        createdQuoteId = updated.id;
        createdQuoteVersion = updated.version;
        quoteRef = updated.quote_ref_no;
      } else {
        const created = await createQuote(payload);
        createdQuoteId = created.id;
        createdQuoteVersion = created.version;
        quoteRef = created.quote_ref_no;
      }

      await saveQuoteStatus(createdQuoteId, createdQuoteVersion);

      localStorage.removeItem('quote_wizard_backup');
      navigate('/quotes');
    } catch (err) {
      console.error("Save final failed:", err);
      if (createdQuoteId) {
        setError(`Draft quote saved (Ref: ${quoteRef}) but finalization failed: ${err.message}`);
      } else {
        setError(err.message || 'Failed to finalize quote. Please try again.');
      }
      setIsSaving(false);
      setSaveAction(null);
    }
  };

  useEffect(() => {
    let isMounted = true;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);

        const payload = {
          client_name: draftQuote.client_name,
          attention: draftQuote.attention || undefined,
          description: draftQuote.description || undefined,
          region_id: draftQuote.region_id === '' ? undefined : Number(draftQuote.region_id),
          solution_id: draftQuote.solution_id === '' ? undefined : Number(draftQuote.solution_id),
          requirement_data: {
            ...draftQuote.requirement_data,
            studios: Array.isArray(draftQuote.studios) ? draftQuote.studios : []
          }
        };

        console.log("Sending preview payload:", payload);

        const [previewResponse, regionsResponse, solutionsResponse] = await Promise.all([
          previewQuote(payload),
          regionApi.getRegions().catch(e => {
            console.warn("Failed to get regions:", e);
            return [];
          }),
          solutionApi.getSolutions().catch(e => {
            console.warn("Failed to get solutions:", e);
            return [];
          })
        ]);

        if (isMounted) {
          setPreviewData(previewResponse);
          setRegions(regionsResponse);
          setSolutions(solutionsResponse);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          console.error("Preview data fetch failed:", err);
          setError(err.message || 'Failed to generate quote preview. Please try again.');
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [draftQuote, retryTrigger]);

  if (loading) {
    return (
      <div className="card">
        <div className="card-body text-center py-5">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Calculating quote...</span>
          </div>
          <p className="mt-3">Generating professional quotation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card border-danger">
        <div className="card-header bg-danger text-white">
          <h5 className="mb-0">Preview Generation Failed</h5>
        </div>
        <div className="card-body">
          <p className="text-danger">{error}</p>
          <div className="mt-4">
            <button className="btn btn-secondary" onClick={onBack}>
              &larr; Back to Studios
            </button>
            <button className="btn btn-primary ms-2" onClick={() => setRetryTrigger(prev => prev + 1)}>
              Retry Calculation
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!previewData) {
    return null;
  }

  // Lookups
  const getRegionName = (id) => {
    const r = regions.find(x => x.id === parseInt(id, 10));
    return r ? r.country_name : id;
  };
  const getSolutionName = (id) => {
    const s = solutions.find(x => x.id === parseInt(id, 10));
    return s ? s.name : id;
  };

  const formatMoney = (amount) => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: previewData.currency_code || 'USD'
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

  const hasCostData = previewData.subtotal_cost_usd !== null && previewData.subtotal_cost_usd !== undefined;

  // Group line items by section
  const groupedLineItems = {};
  if (previewData.line_items) {
    previewData.line_items.forEach(item => {
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
        <h2 className="preview-title">Quote Preview</h2>
        <p className="preview-subtitle">Review the complete quotation before saving.</p>
      </div>

      {/* QUOTE META HEADER */}
      <div className="quote-meta-header">
        <div className="meta-item">
          <div className="meta-label">Quote #</div>
          <div className="meta-value">{previewData.quote_ref_no || 'PREVIEW'}</div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Status</div>
          <div className="meta-value">
            <span className={`badge ${previewData.status === 'SAVED' ? 'badge-success' : (previewData.status === 'DRAFT' ? 'badge-warning' : 'badge-neutral')}`}>
              {previewData.status ? previewData.status.toUpperCase() : 'PREVIEW'}
            </span>
          </div>
        </div>
        <div className="meta-item">
          <div className="meta-label">Date</div>
          <div className="meta-value">{previewData.date ? new Date(previewData.date).toLocaleDateString() : new Date().toLocaleDateString()}</div>
        </div>
      </div>

      {/* CUSTOMER & QUOTE INFO */}
      <div className="info-panels">
        <div className="info-panel">
          <h3 className="section-title">Customer Information</h3>
          <dl className="info-list">
            <dt>Customer</dt>
            <dd>{previewData.client_name}</dd>
            {previewData.attention && (
              <>
                <dt>Attention</dt>
                <dd>{previewData.attention}</dd>
              </>
            )}
            {previewData.description && (
              <>
                <dt>Description</dt>
                <dd className="text-sm">{previewData.description}</dd>
              </>
            )}
          </dl>
        </div>
        <div className="info-panel">
          <h3 className="section-title">Quote Details</h3>
          <dl className="info-list">
            <dt>Region</dt>
            <dd>{getRegionName(previewData.region_id)}</dd>
            <dt>Solution</dt>
            <dd>{getSolutionName(previewData.solution_id)}</dd>
            <dt>Currency</dt>
            <dd>{previewData.currency_code}</dd>
            <dt>FX Rate</dt>
            <dd>{parseFloat(previewData.fx_rate_to_usd).toFixed(4)}</dd>
            <dt>Tax</dt>
            <dd>{previewData.tax_enabled ? `Yes (${parseFloat(previewData.tax_rate_percent)}%)` : 'No'}</dd>
          </dl>
        </div>
      </div>

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
                        <td style={{ textAlign: 'center' }} className="text-gray-500 text-sm">{item.sort_order}</td>
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
                    <div className="text-gray-500">No line items generated</div>
                    <div className="text-sm text-gray-500 mt-3">The current requirements did not produce any billable items.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* PRICING SUMMARY */}
      <div className="financial-summary-section">
        <div className="financial-summary-card">
          <h3 className="section-title">Pricing Summary</h3>
          <table className="financial-table">
            <tbody>
              {hasCostData && (
                <tr>
                  <td>Total Cost (USD)</td>
                  <td className="text-right font-medium text-gray-900">{formatUsd(previewData.subtotal_cost_usd)}</td>
                </tr>
              )}
              <tr>
                <td>Subtotal Sell (USD)</td>
                <td className="text-right font-medium text-gray-900">{formatUsd(previewData.subtotal_sell_usd)}</td>
              </tr>
              <tr>
                <td>Tax Amount ({previewData.currency_code})</td>
                <td className="text-right font-medium text-gray-900">{formatMoney(previewData.tax_amount)}</td>
              </tr>
              <tr className="total-row">
                <td className="font-bold text-lg">TOTAL SELL</td>
                <td className="text-right font-bold text-2xl total-value">{formatMoney(previewData.total_sell_local)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* BUTTON AREA */}
      <div className="preview-actions">
        <div className="action-left">
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={onBack}
            disabled={isSaving}
          >
            Back to Studios
          </button>
        </div>
        <div className="action-right">
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={handleSaveDraft}
            disabled={isSaving}
          >
            {isSaving && saveAction === 'draft' ? 'Saving...' : 'Save as Draft'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-lg"
            onClick={handleSaveFinal}
            disabled={isSaving}
          >
            {isSaving && saveAction === 'final' ? 'Finalizing...' : 'Save Final Quote'}
          </button>
        </div>
      </div>
    </div>
  );
}
