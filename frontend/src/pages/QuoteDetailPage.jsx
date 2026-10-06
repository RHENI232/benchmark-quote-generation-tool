import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getQuote } from '../api/quoteApi';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';

export default function QuoteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchQuoteDetails() {
      try {
        setLoading(true);
        setError(null);
        const data = await getQuote(id);
        setQuote(data);
      } catch (err) {
        console.error('Failed to fetch quote details:', err);
        setError(err.message || 'Failed to load quote details.');
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      fetchQuoteDetails();
    }
  }, [id]);

  if (loading) {
    return (
      <div className="p-4">
        <PageHeader title="Quote Details" />
        <div className="card mt-4 p-5 text-center">
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
      <div className="p-4">
        <PageHeader title="Quote Details" />
        <div className="card border-danger mt-4">
          <div className="card-header bg-danger text-white">Error</div>
          <div className="card-body">
            <p className="text-danger">{error || 'Quote not found.'}</p>
            <button className="btn btn-secondary" onClick={() => navigate('/quotes')}>
              Back to Quotes
            </button>
          </div>
        </div>
      </div>
    );
  }

  const formatUsd = (amount) => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(num);
  };

  const formatMoney = (amount, currency = 'USD') => {
    if (amount == null) return '-';
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
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

  return (
    <div className="p-4">
      <PageHeader
        title={`Quote: ${quote.quote_ref_no || `QT-${quote.id}`}`}
        subtitle="Read-only view of the generated quote."
        actions={
          <div className="d-flex gap-2">
            {quote.status === 'draft' && (
              <button className="btn btn-primary" onClick={() => navigate(`/quotes/${quote.id}/edit`)}>
                Edit Quote
              </button>
            )}
            <button className="btn btn-secondary" onClick={() => navigate('/quotes')}>
              Back to Quotes
            </button>
          </div>
        }
      />

      <div className="row mt-4">
        <div className="col-md-6 mb-4">
          <div className="card h-100">
            <div className="card-header bg-light">
              <h5 className="mb-0">Client Information</h5>
            </div>
            <div className="card-body">
              <dl className="row mb-0">
                <dt className="col-sm-4">Client Name</dt>
                <dd className="col-sm-8">{quote.client_name}</dd>

                <dt className="col-sm-4">Attention</dt>
                <dd className="col-sm-8">{quote.attention || '-'}</dd>

                <dt className="col-sm-4">Description</dt>
                <dd className="col-sm-8">{quote.description || '-'}</dd>

                <dt className="col-sm-4">Status</dt>
                <dd className="col-sm-8"><StatusBadge status={quote.status} /></dd>
              </dl>
            </div>
          </div>
        </div>

        <div className="col-md-6 mb-4">
          <div className="card h-100">
            <div className="card-header bg-light">
              <h5 className="mb-0">Financial Summary</h5>
            </div>
            <div className="card-body">
              <dl className="row mb-0">
                <dt className="col-sm-5">Currency</dt>
                <dd className="col-sm-7">{quote.currency_code || 'USD'}</dd>

                <dt className="col-sm-5">FX Rate (to USD)</dt>
                <dd className="col-sm-7">{quote.fx_rate_to_usd ? parseFloat(quote.fx_rate_to_usd).toFixed(4) : '-'}</dd>

                {hasCostData && (
                  <>
                    <dt className="col-sm-5">Total Cost (USD)</dt>
                    <dd className="col-sm-7">{formatUsd(quote.subtotal_cost_usd)}</dd>
                  </>
                )}

                <dt className="col-sm-5">Subtotal Sell (USD)</dt>
                <dd className="col-sm-7">{formatUsd(quote.subtotal_sell_usd)}</dd>

                <dt className="col-sm-5">Tax Amount ({quote.currency_code})</dt>
                <dd className="col-sm-7">{formatMoney(quote.tax_amount, quote.currency_code)}</dd>

                <dt className="col-sm-5 fs-5">Total Sell ({quote.currency_code})</dt>
                <dd className="col-sm-7 fs-5 fw-bold text-primary">{formatMoney(quote.total_sell_local, quote.currency_code)}</dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      <div className="card mb-4 shadow-sm">
        <div className="card-header bg-light">
          <h5 className="mb-0">Line Items</h5>
        </div>
        <div className="card-body p-0">
          <div className="table-responsive">
            <table className="table table-hover table-bordered mb-0 align-middle">
              <thead className="table-light">
                <tr>
                  <th style={{width: '5%'}}>#</th>
                  <th style={{width: '15%'}}>Section</th>
                  <th style={{width: '35%'}}>Description</th>
                  <th style={{width: '5%'}} className="text-center">Qty</th>
                  {hasCostData && <th style={{width: '10%'}} className="text-end">Unit Cost</th>}
                  <th style={{width: '10%'}} className="text-end">Unit Sell</th>
                  {hasCostData && <th style={{width: '10%'}} className="text-end">Margin</th>}
                  <th style={{width: '10%'}} className="text-end">Total Sell</th>
                </tr>
              </thead>
              <tbody>
                {quote.line_items && quote.line_items.length > 0 ? (
                  quote.line_items.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.sort_order}</td>
                      <td>
                        <span className="badge bg-secondary">{item.section}</span>
                      </td>
                      <td>
                        <div className="fw-bold">{item.part_number || 'Custom'}</div>
                        <div className="small text-muted">{item.description}</div>
                        {item.brand && <div className="small text-muted fst-italic">Brand: {item.brand}</div>}
                      </td>
                      <td className="text-center">{item.quantity}</td>
                      {hasCostData && <td className="text-end text-muted">{formatUsd(item.unit_cost_price_snapshot)}</td>}
                      <td className="text-end">{formatUsd(item.unit_sell_price_snapshot)}</td>
                      {hasCostData && <td className="text-end">{formatPercent(item.margin_percent)}</td>}
                      <td className="text-end fw-semibold">{formatUsd(item.line_sell_total)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={hasCostData ? 8 : 5} className="text-center py-4 text-muted">
                      No line items generated for this quote.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
