import React, { useState, useEffect, useCallback } from 'react';
import { getQuotes } from '../api/quoteApi';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import '../styles/quotes.css';

const LIMIT = 10;

export default function QuoteListPage() {
  const [quotes, setQuotes] = useState([]);
  const [skip, setSkip] = useState(0);
  const [clientName, setClientName] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchQuotes = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await getQuotes({ skip, limit: LIMIT, clientName });
      setQuotes(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch quotes.');
    } finally {
      setIsLoading(false);
    }
  }, [skip, clientName]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setSkip(0);
    setClientName(searchInput);
  };

  const handleNext = () => {
    setSkip((prev) => prev + LIMIT);
  };

  const handlePrev = () => {
    setSkip((prev) => Math.max(0, prev - LIMIT));
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="quotes-container">
      <PageHeader
        title="Quotes"
        subtitle="Manage and view generated customer quotes."
      />

      <div className="card quotes-toolbar">
        <form onSubmit={handleSearchSubmit} className="search-form">
          <div className="search-input-wrapper">
            <input
              type="text"
              className="form-input"
              placeholder="Search by Client Name..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">Search</button>
          {clientName && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setSearchInput('');
                setClientName('');
                setSkip(0);
              }}
            >
              Clear Filter
            </button>
          )}
        </form>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="table-container mb-4">
        <table className="data-table">
          <thead>
            <tr>
              <th>Quote Ref</th>
              <th>Client Name</th>
              <th>Region</th>
              <th>Generated Date</th>
              <th>Status</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan="6" className="table-state-cell">
                  <div className="spinner"></div> Loading quotes...
                </td>
              </tr>
            ) : quotes.length === 0 ? (
              <tr>
                <td colSpan="6" className="table-state-cell">
                  <div className="text-gray-500">No quotes found matching your criteria.</div>
                </td>
              </tr>
            ) : (
              quotes.map((quote) => (
                <tr key={quote.id}>
                  <td className="font-medium text-gray-900">{quote.quote_reference || `QT-${quote.id}`}</td>
                  <td>{quote.client_name}</td>
                  <td>{quote.region_id}</td>
                  <td>{formatDate(quote.created_at)}</td>
                  <td><StatusBadge status={quote.status} /></td>
                  <td className="text-right">
                    <button className="btn-link">View Details</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination-wrapper">
        <span className="page-info">
          Showing <span className="font-medium">{quotes.length > 0 ? skip + 1 : 0}</span> to <span className="font-medium">{skip + quotes.length}</span> results
        </span>
        <div className="pagination-controls">
          <button
            onClick={handlePrev}
            disabled={skip === 0 || isLoading}
            className="btn btn-secondary"
          >
            Previous
          </button>
          <button
            onClick={handleNext}
            disabled={quotes.length < LIMIT || isLoading}
            className="btn btn-secondary"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
