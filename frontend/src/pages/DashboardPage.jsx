import React, { useState, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { Link } from 'react-router-dom';
import { getQuotes } from '../api/quoteApi';
import PageHeader from '../components/common/PageHeader';
import StatusBadge from '../components/common/StatusBadge';
import '../styles/dashboard.css';

export default function DashboardPage() {
  const { user } = useAuth();
  const [recentQuotes, setRecentQuotes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchRecent() {
      try {
        const data = await getQuotes({ skip: 0, limit: 5 });
        setRecentQuotes(data);
      } catch (err) {
        console.error("Failed to load recent quotes", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchRecent();
  }, []);

  const totalQuotes = recentQuotes.length > 0 ? recentQuotes.length + "+" : 0;

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="dashboard-container">
      <PageHeader
        title="Dashboard"
        subtitle="Overview of quotation activity and recent work."
      />

      <div className="dashboard-kpi-grid">
        <div className="card kpi-card">
          <div className="kpi-label">Recent Quotes Activity</div>
          <div className="kpi-value">{totalQuotes}</div>
          <div className="kpi-subtext">Latest visible in your pipeline</div>
        </div>
      </div>

      <div className="dashboard-recent">
        <div className="recent-header">
          <div>
            <h2 className="text-lg font-semibold">Recent Quotes</h2>
            <p className="text-sm text-gray-500">Your most recently generated or updated quotes.</p>
          </div>
          <Link to="/quotes" className="btn btn-secondary">View all quotes</Link>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Quote Ref</th>
                <th>Client</th>
                <th>Region</th>
                <th>Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="p-4 text-center text-gray-500">Loading recent quotes...</td>
                </tr>
              ) : recentQuotes.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-4 text-center text-gray-500">No quotes found.</td>
                </tr>
              ) : (
                recentQuotes.map((quote) => (
                  <tr key={quote.id}>
                    <td className="font-medium">{quote.quote_reference || `QT-${quote.id}`}</td>
                    <td>{quote.client_name}</td>
                    <td>{quote.region_id}</td>
                    <td>{formatDate(quote.created_at)}</td>
                    <td><StatusBadge status={quote.status} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
