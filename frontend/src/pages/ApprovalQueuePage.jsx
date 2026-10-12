import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApprovalQueue } from '../api/quoteApi';
import { regionApi } from '../api/regionApi';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import { useAuth, PERMISSIONS } from '../auth/AuthContext';
import '../styles/quotes.css';

export default function ApprovalQueuePage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [quotes, setQuotes] = useState([]);
  const [regions, setRegions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchQueue = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [quotesData, regionsData] = await Promise.all([
        getApprovalQueue(),
        regionApi.getRegions().catch(e => {
          console.warn("Failed to get regions:", e);
          return [];
        })
      ]);
      setQuotes(quotesData);
      setRegions(regionsData);
    } catch (err) {
      setError(err.message || 'Failed to fetch approval queue.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getRegionName = (regionId) => {
    const region = regions.find((r) => r.id === regionId);
    return region ? region.country_name : regionId;
  };

  const formatMoney = (amount, currencyCode) => {
    if (amount == null || amount === '') return 'N/A';
    const num = parseFloat(amount);
    if (isNaN(num)) return 'N/A';
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currencyCode || 'USD'
      }).format(num);
    } catch {
      return `${currencyCode || 'USD'} ${num.toFixed(2)}`;
    }
  };

  return (
    <div className="quotes-container">
      <PageHeader
        title="Approval Queue"
        subtitle="Review quotes pending your approval."
      />

      {error && <div className="error-banner">{error}</div>}

      <div className="table-container mb-4">
        <table className="data-table">
          <thead>
            <tr>
              <th>Quote Ref</th>
              <th>Urgent</th>
              <th>Client Name</th>
              <th>Region</th>
              {hasPermission(PERMISSIONS.COST_VISIBILITY) && <th>Total Sell</th>}
              <th>Submitted</th>
              <th>Status</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={hasPermission(PERMISSIONS.COST_VISIBILITY) ? "8" : "7"} className="table-state-cell">
                  <div className="spinner"></div> Loading queue...
                </td>
              </tr>
            ) : quotes.length === 0 ? (
              <tr>
                <td colSpan={hasPermission(PERMISSIONS.COST_VISIBILITY) ? "8" : "7"} className="table-state-cell">
                  <div className="text-gray-500">No quotes pending approval.</div>
                </td>
              </tr>
            ) : (
              quotes.map((quote) => (
                <tr key={quote.id}>
                  <td className="font-medium text-gray-900">{quote.quote_ref_no || `QT-${quote.id}`}</td>
                  <td>
                    {quote.is_urgent ? (
                      <span className="badge badge-danger">Urgent</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td>{quote.client_name}</td>
                  <td>{getRegionName(quote.region_id)}</td>
                  {hasPermission(PERMISSIONS.COST_VISIBILITY) && (
                    <td>
                      {formatMoney(quote.total_sell_local, quote.currency_code)}
                    </td>
                  )}
                  <td>{formatDate(quote.updated_at || quote.created_at)}</td>
                  <td><StatusBadge status={quote.status} /></td>
                  <td className="text-right">
                    <button
                      className="btn-link"
                      onClick={() => navigate(`/quotes/${quote.id}`)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

