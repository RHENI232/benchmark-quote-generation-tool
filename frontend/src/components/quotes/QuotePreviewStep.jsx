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
      <div className="quotation-header text-center mb-5">
        <h2 className="text-uppercase fw-bold text-dark mb-1">Benchmark Broadcast Systems</h2>
        <h4 className="text-muted fw-light mb-4">PRESALES QUOTATION</h4>

        <div className="d-flex justify-content-center align-items-center gap-4">
          <div>
            <div className="text-muted small text-uppercase">Quote Reference</div>
            <div className="fs-5 fw-bold text-dark">{previewData.quote_ref_no || 'PREVIEW'}</div>
          </div>
          <div className="border-start ps-4">
            <div className="text-muted small text-uppercase">Status</div>
            <div className="fs-5 fw-bold text-primary">PREVIEW</div>
          </div>
          {previewData.date && (
            <div className="border-start ps-4">
              <div className="text-muted small text-uppercase">Date</div>
              <div className="fs-5 fw-bold text-dark">{new Date(previewData.date).toLocaleDateString()}</div>
            </div>
          )}
        </div>
      </div>

      {/* CUSTOMER & QUOTE INFO */}
      <div className="row mb-5">
        <div className="col-md-6">
          <div className="card h-100 border-0 shadow-sm">
            <div className="card-header bg-white border-bottom-0 pt-4 pb-0">
              <h6 className="text-uppercase text-muted fw-bold mb-0">Customer</h6>
            </div>
            <div className="card-body">
              <div className="fs-5 fw-bold mb-2">{previewData.client_name}</div>
              {previewData.attention && <div className="mb-1 text-dark"><strong>Attn:</strong> {previewData.attention}</div>}
              {previewData.description && <div className="text-muted small">{previewData.description}</div>}
            </div>
          </div>
        </div>
        <div className="col-md-6 mt-4 mt-md-0">
          <div className="card h-100 border-0 shadow-sm">
            <div className="card-header bg-white border-bottom-0 pt-4 pb-0">
              <h6 className="text-uppercase text-muted fw-bold mb-0">Quote Details</h6>
            </div>
            <div className="card-body">
              <table className="table table-sm table-borderless mb-0">
                <tbody>
                  <tr>
                    <td className="text-muted ps-0 py-1" style={{ width: '40%' }}>Region</td>
                    <td className="fw-medium text-dark py-1">{getRegionName(previewData.region_id)}</td>
                  </tr>
                  <tr>
                    <td className="text-muted ps-0 py-1">Solution</td>
                    <td className="fw-medium text-dark py-1">{getSolutionName(previewData.solution_id)}</td>
                  </tr>
                  <tr>
                    <td className="text-muted ps-0 py-1">Currency</td>
                    <td className="fw-medium text-dark py-1">{previewData.currency_code}</td>
                  </tr>
                  <tr>
                    <td className="text-muted ps-0 py-1">FX Rate (to USD)</td>
                    <td className="fw-medium text-dark py-1">{parseFloat(previewData.fx_rate_to_usd).toFixed(4)}</td>
                  </tr>
                  <tr>
                    <td className="text-muted ps-0 py-1">Tax Enabled</td>
                    <td className="fw-medium text-dark py-1">{previewData.tax_enabled ? `Yes (${parseFloat(previewData.tax_rate_percent)}%)` : 'No'}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* LINE ITEMS */}
      <div className="mb-5">
        <h5 className="text-uppercase text-muted fw-bold mb-3 px-2">Line Items</h5>
        <div className="card border-0 shadow-sm overflow-hidden">
          <div className="table-responsive">
            <table className="table table-hover mb-0 align-middle quotation-table">
              <thead className="table-light text-uppercase small text-muted">
                <tr>
                  <th className="ps-4" style={{width: '5%'}}>#</th>
                  <th style={{width: '15%'}}>Part Number</th>
                  <th style={{width: '30%'}}>Description</th>
                  <th className="text-center" style={{width: '5%'}}>Qty</th>
                  {hasCostData && <th className="text-end" style={{width: '12%'}}>Unit Cost</th>}
                  <th className="text-end" style={{width: '12%'}}>Unit Sell</th>
                  {hasCostData && <th className="text-end" style={{width: '8%'}}>Margin</th>}
                  <th className="text-end pe-4" style={{width: '13%'}}>Total Sell</th>
                </tr>
              </thead>
              <tbody>
                {sections.length > 0 ? (
                  sections.map((sectionName) => (
                    <React.Fragment key={sectionName}>
                      {/* Section Header Row */}
                      <tr className="bg-light">
                        <td colSpan={hasCostData ? 8 : 6} className="fw-bold text-dark ps-4 py-3">
                          {sectionName}
                        </td>
                      </tr>
                      {/* Section Items */}
                      {groupedLineItems[sectionName].map((item, idx) => (
                        <tr key={`${sectionName}-${idx}`}>
                          <td className="ps-4 text-muted small">{item.sort_order}</td>
                          <td>
                            <div className="fw-medium text-dark">{item.part_number || 'Custom'}</div>
                            {item.brand && <div className="small text-muted">{item.brand}</div>}
                          </td>
                          <td>
                            <div className="text-dark small lh-sm">{item.description}</div>
                          </td>
                          <td className="text-center fw-medium">{item.quantity}</td>
                          {hasCostData && <td className="text-end text-muted small">{formatUsd(item.unit_cost_price_snapshot)}</td>}
                          <td className="text-end small">{formatUsd(item.unit_sell_price_snapshot)}</td>
                          {hasCostData && <td className="text-end small">{formatPercent(item.margin_percent)}</td>}
                          <td className="text-end pe-4 fw-medium text-dark">{formatUsd(item.line_sell_total)}</td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={hasCostData ? 8 : 6} className="text-center py-5 text-muted">
                      No line items generated for these requirements.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* PRICING SUMMARY */}
      <div className="row justify-content-end mb-5">
        <div className="col-lg-5 col-md-7">
          <div className="card border-0 shadow-sm bg-light">
            <div className="card-body p-4">
              <h5 className="text-uppercase text-muted fw-bold border-bottom pb-3 mb-3">Pricing Summary</h5>
              <table className="table table-borderless table-sm mb-0">
                <tbody>
                  {hasCostData && (
                    <tr>
                      <td className="text-muted ps-0">Total Cost (USD)</td>
                      <td className="text-end pe-0 fw-medium text-dark">{formatUsd(previewData.subtotal_cost_usd)}</td>
                    </tr>
                  )}
                  <tr>
                    <td className="text-muted ps-0">Subtotal Sell (USD)</td>
                    <td className="text-end pe-0 fw-medium text-dark">{formatUsd(previewData.subtotal_sell_usd)}</td>
                  </tr>
                  <tr>
                    <td className="text-muted ps-0 border-bottom pb-3">Tax Amount ({previewData.currency_code})</td>
                    <td className="text-end pe-0 fw-medium text-dark border-bottom pb-3">{formatMoney(previewData.tax_amount)}</td>
                  </tr>
                  <tr>
                    <td className="ps-0 pt-3 fs-5 fw-bold text-dark">TOTAL SELL</td>
                    <td className="text-end pe-0 pt-3 fs-4 fw-bold text-primary">{formatMoney(previewData.total_sell_local)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* BUTTON AREA */}
      <div className="d-flex flex-column flex-md-row justify-content-between align-items-center mt-5 pt-4 border-top gap-3">
        <button
          type="button"
          className="btn btn-outline-secondary btn-lg order-2 order-md-1 px-4"
          onClick={onBack}
          disabled={isSaving}
        >
          &larr; Back to Studios
        </button>
        <div className="d-flex gap-3 w-100 w-md-auto justify-content-end order-1 order-md-2">
          <button
            type="button"
            className="btn btn-secondary btn-lg flex-grow-1 flex-md-grow-0 px-4"
            onClick={handleSaveDraft}
            disabled={isSaving}
          >
            {isSaving && saveAction === 'draft' ? 'Saving...' : 'Save as Draft'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-lg flex-grow-1 flex-md-grow-0 px-4"
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
