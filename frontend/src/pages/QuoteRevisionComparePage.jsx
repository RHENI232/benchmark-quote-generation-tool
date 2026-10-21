import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { getQuoteRevisions, compareQuoteRevisions } from '../api/quoteApi';
import { useAuth, PERMISSIONS } from '../auth/AuthContext';
import {
  getActionBadgeClass,
  formatActionLabel,
  formatRevisionDate,
  formatSnapshotUsd,
  formatSnapshotPercent,
  getLineItemCategoryBadge,
  formatFieldDiffValue,
  getSnapshotViewUrl,
  validateComparisonParams,
  filterFinancialChanges,
  classifyComparisonError,
} from '../utils/revisionFormatters';
import '../styles/wizard.css';

export default function QuoteRevisionComparePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasPermission } = useAuth();

  const userHasCostVisibility = hasPermission(PERMISSIONS.COST_VISIBILITY);

  // Available revisions for dropdowns
  const [availableRevisions, setAvailableRevisions] = useState([]);
  const [revisionsLoading, setRevisionsLoading] = useState(true);

  // URL Query Parameters: support primary 'from' & 'to', with fallbacks to legacy aliases
  const queryFrom = searchParams.get('from') || searchParams.get('base_revision') || searchParams.get('from_revision');
  const queryTo = searchParams.get('to') || searchParams.get('target_revision') || searchParams.get('to_revision');

  const [baseRevNum, setBaseRevNum] = useState(null);
  const [targetRevNum, setTargetRevNum] = useState(null);

  // Comparison response & state
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Filter tab for line items: 'all' | 'added' | 'removed' | 'modified' | 'unchanged'
  const [activeTab, setActiveTab] = useState('all');

  // Token ref to prevent out-of-order stale comparison responses
  const activeComparisonRef = useRef(0);

  // Run backend comparison
  const runComparison = useCallback(
    async (base, target) => {
      if (!id || base == null || target == null) return;

      const validation = validateComparisonParams(base, target);
      if (!validation.isValid) {
        setValidationError(validation.error);
        setComparison(null);
        return;
      }

      setValidationError(null);
      setComparing(true);
      setError(null);
      const reqToken = ++activeComparisonRef.current;

      try {
        const result = await compareQuoteRevisions(id, base, target);
        if (reqToken === activeComparisonRef.current) {
          setComparison(result);
          // Sync URL with standard ?from=X&to=Y
          setSearchParams({ from: String(base), to: String(target) });
        }
      } catch (err) {
        if (reqToken === activeComparisonRef.current) {
          console.error('Comparison error:', err);
          setError(classifyComparisonError(err, base, target));
          setComparison(null);
        }
      } finally {
        if (reqToken === activeComparisonRef.current) {
          setComparing(false);
        }
      }
    },
    [id, setSearchParams]
  );

  // Load available revisions and set initial comparison selection
  useEffect(() => {
    let isMounted = true;
    async function fetchRevisionsList() {
      setRevisionsLoading(true);
      setError(null);
      try {
        const revs = await getQuoteRevisions(id, { order: 'asc' });
        if (!isMounted) return;
        const list = Array.isArray(revs) ? revs : [];
        setAvailableRevisions(list);

        // Parameter validation if query parameters are present in URL
        if (queryFrom !== null || queryTo !== null) {
          const valResult = validateComparisonParams(queryFrom, queryTo);
          if (!valResult.isValid) {
            if (!valResult.isMissing) {
              setValidationError(valResult.error);
            }
            if (valResult.isDistinctError) {
              setBaseRevNum(valResult.from);
              setTargetRevNum(valResult.to);
            }
          } else {
            setBaseRevNum(valResult.from);
            setTargetRevNum(valResult.to);
            setValidationError(null);
            runComparison(valResult.from, valResult.to);
          }
        } else if (list.length >= 2) {
          // Graceful default: compare second-to-last with latest revision
          const defaultBase = list[list.length - 2].revision_number;
          const defaultTarget = list[list.length - 1].revision_number;
          setBaseRevNum(defaultBase);
          setTargetRevNum(defaultTarget);
          setSearchParams({ from: String(defaultBase), to: String(defaultTarget) });
          runComparison(defaultBase, defaultTarget);
        } else if (list.length === 1) {
          setBaseRevNum(list[0].revision_number);
          setTargetRevNum(list[0].revision_number);
          setValidationError('At least two historical revisions are required to perform a revision comparison.');
        }
      } catch (err) {
        if (isMounted) {
          console.error('Failed to load revision list for comparison:', err);
          setError(classifyComparisonError(err));
        }
      } finally {
        if (isMounted) setRevisionsLoading(false);
      }
    }
    if (id) fetchRevisionsList();
    return () => {
      isMounted = false;
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSwap = () => {
    if (baseRevNum && targetRevNum && baseRevNum !== targetRevNum) {
      const newBase = targetRevNum;
      const newTarget = baseRevNum;
      setBaseRevNum(newBase);
      setTargetRevNum(newTarget);
      setSearchParams({ from: String(newBase), to: String(newTarget) });
      runComparison(newBase, newTarget);
    }
  };

  const handleBaseChange = (e) => {
    const val = parseInt(e.target.value, 10);
    setBaseRevNum(val);
    if (val === targetRevNum) {
      setValidationError('Base and target revisions must be distinct. Please select two different revisions to compare.');
      setComparison(null);
    } else {
      setValidationError(null);
      if (targetRevNum) {
        setSearchParams({ from: String(val), to: String(targetRevNum) });
        runComparison(val, targetRevNum);
      }
    }
  };

  const handleTargetChange = (e) => {
    const val = parseInt(e.target.value, 10);
    setTargetRevNum(val);
    if (val === baseRevNum) {
      setValidationError('Base and target revisions must be distinct. Please select two different revisions to compare.');
      setComparison(null);
    } else {
      setValidationError(null);
      if (baseRevNum) {
        setSearchParams({ from: String(baseRevNum), to: String(val) });
        runComparison(baseRevNum, val);
      }
    }
  };

  // Safe filtered financial changes (strict cost masking)
  const safeFinancialChanges = comparison
    ? filterFinancialChanges(comparison.financial_changes, userHasCostVisibility)
    : {};

  return (
    <div className="preview-step-container">
      {/* PAGE HEADER */}
      <div className="preview-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 className="preview-title">Quote Revision Comparison</h2>
            <p className="preview-subtitle">
              Inspect historical field deltas and Bill of Quantities differences between two saved revisions.
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

      {/* REVISION SELECTION & CONTROLS TOOLBAR */}
      <div
        className="card mb-4"
        style={{
          padding: '1.25rem',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            {/* BASE REVISION SELECTOR */}
            <div>
              <label
                htmlFor="select-base-revision"
                style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.25rem' }}
              >
                Base Revision (From)
              </label>
              <select
                id="select-base-revision"
                value={baseRevNum || ''}
                onChange={handleBaseChange}
                disabled={revisionsLoading || comparing || availableRevisions.length === 0}
                style={{
                  padding: '0.45rem 0.75rem',
                  borderRadius: '0.375rem',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  fontSize: '0.875rem',
                  minWidth: '220px',
                }}
                aria-label="Select base revision"
              >
                {availableRevisions.length === 0 ? (
                  <option value="">No revisions available</option>
                ) : (
                  availableRevisions.map((r) => (
                    <option key={`base-${r.revision_number}`} value={r.revision_number}>
                      Rev #{r.revision_number} (v{r.quote_version}) — {formatActionLabel(r.action)}
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* SWAP BUTTON */}
            <div style={{ alignSelf: 'flex-end' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleSwap}
                disabled={revisionsLoading || comparing || !baseRevNum || !targetRevNum || baseRevNum === targetRevNum}
                title="Swap Base and Target revisions"
                style={{ padding: '0.45rem 0.75rem', minHeight: '34px' }}
              >
                ⇄ Swap
              </button>
            </div>

            {/* TARGET REVISION SELECTOR */}
            <div>
              <label
                htmlFor="select-target-revision"
                style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.25rem' }}
              >
                Target Revision (To)
              </label>
              <select
                id="select-target-revision"
                value={targetRevNum || ''}
                onChange={handleTargetChange}
                disabled={revisionsLoading || comparing || availableRevisions.length === 0}
                style={{
                  padding: '0.45rem 0.75rem',
                  borderRadius: '0.375rem',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  fontSize: '0.875rem',
                  minWidth: '220px',
                }}
                aria-label="Select target revision"
              >
                {availableRevisions.length === 0 ? (
                  <option value="">No revisions available</option>
                ) : (
                  availableRevisions.map((r) => (
                    <option key={`target-${r.revision_number}`} value={r.revision_number}>
                      Rev #{r.revision_number} (v{r.quote_version}) — {formatActionLabel(r.action)}
                    </option>
                  ))
                )}
              </select>
            </div>
          </div>

          {/* QUICK SNAPSHOT LINKS */}
          <div style={{ display: 'flex', gap: '0.5rem', alignSelf: 'flex-end', flexWrap: 'wrap' }}>
            {baseRevNum && (
              <button
                type="button"
                className="btn btn-outline-secondary btn-sm"
                onClick={() => navigate(getSnapshotViewUrl(id, baseRevNum))}
                style={{ fontSize: '0.75rem' }}
              >
                View Base Rev #{baseRevNum}
              </button>
            )}
            {targetRevNum && (
              <button
                type="button"
                className="btn btn-outline-secondary btn-sm"
                onClick={() => navigate(getSnapshotViewUrl(id, targetRevNum))}
                style={{ fontSize: '0.75rem' }}
              >
                View Target Rev #{targetRevNum}
              </button>
            )}
          </div>
        </div>

        {/* VALIDATION WARNING BANNER */}
        {validationError && (
          <div
            style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              backgroundColor: '#fffbeb',
              border: '1px solid #fef3c7',
              borderRadius: '0.375rem',
              color: '#92400e',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span>⚠️</span>
            <span>{validationError}</span>
          </div>
        )}
      </div>

      {/* ERROR STATE */}
      {error && (
        <div className="card border-danger mb-4" style={{ padding: '1.25rem', backgroundColor: '#fef2f2', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ color: '#991b1b', fontSize: '0.875rem' }}>
              <strong>Comparison Error:</strong> {error}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {error.includes('session has expired') && (
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={() => navigate('/login')}
                >
                  Sign In
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => runComparison(baseRevNum, targetRevNum)}
                disabled={comparing || !baseRevNum || !targetRevNum || baseRevNum === targetRevNum}
              >
                Retry Comparison
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EMPTY / LOADING STATES */}
      {revisionsLoading ? (
        <div className="card" style={{ padding: '3rem 1rem', textAlign: 'center', marginBottom: '1.5rem' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem auto' }}></div>
          <p style={{ color: '#4b5563', fontSize: '0.9375rem' }}>Loading revision history...</p>
        </div>
      ) : availableRevisions.length === 0 ? (
        <div className="card" style={{ padding: '3rem 1rem', textAlign: 'center', marginBottom: '1.5rem' }}>
          <p style={{ color: '#64748b', fontSize: '1rem', margin: '0 0 1rem 0' }}>
            No saved revisions were found for Quote #{id}.
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/quotes/${id}`)}
          >
            Return to Quote Details
          </button>
        </div>
      ) : comparing ? (
        <div className="card" style={{ padding: '3rem 1rem', textAlign: 'center', marginBottom: '1.5rem' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem auto' }}></div>
          <p style={{ color: '#4b5563', fontSize: '1rem', fontWeight: 500 }}>
            Comparing Revision #{baseRevNum} with Revision #{targetRevNum}...
          </p>
        </div>
      ) : comparison ? (
        /* COMPARISON RESULTS */
        <div>
          {/* SUMMARY CARDS: BASE VS TARGET */}
          <div className="info-panels" style={{ marginBottom: '1.5rem' }}>
            {/* BASE SUMMARY */}
            <div
              className="info-panel"
              style={{
                borderLeft: '4px solid #64748b',
                backgroundColor: '#f8fafc',
                borderRadius: '0.375rem',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
                  Base Snapshot (From)
                </span>
                <span className={`badge ${getActionBadgeClass(comparison.base_revision.action)}`}>
                  {formatActionLabel(comparison.base_revision.action)}
                </span>
              </div>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.125rem', fontWeight: 600, color: '#1e293b' }}>
                Revision #{comparison.base_revision.revision_number}{' '}
                <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                  v{comparison.base_revision.quote_version}
                </span>
              </h3>
              <dl className="info-list" style={{ fontSize: '0.8125rem' }}>
                <dt>Captured By</dt>
                <dd>
                  {comparison.base_revision.user_email || `User #${comparison.base_revision.user_id}`}
                  {comparison.base_revision.user_role && ` (${comparison.base_revision.user_role})`}
                </dd>
                <dt>Date & Time</dt>
                <dd>{formatRevisionDate(comparison.base_revision.created_at)}</dd>
                {comparison.base_revision.change_reason && (
                  <>
                    <dt>Reason</dt>
                    <dd style={{ fontStyle: 'italic', color: '#475569' }}>
                      "{comparison.base_revision.change_reason}"
                    </dd>
                  </>
                )}
              </dl>
            </div>

            {/* TARGET SUMMARY */}
            <div
              className="info-panel"
              style={{
                borderLeft: '4px solid var(--color-brand-600, #1c3d73)',
                backgroundColor: '#f8fafc',
                borderRadius: '0.375rem',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--color-brand-600, #1c3d73)' }}>
                  Target Snapshot (To)
                </span>
                <span className={`badge ${getActionBadgeClass(comparison.target_revision.action)}`}>
                  {formatActionLabel(comparison.target_revision.action)}
                </span>
              </div>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.125rem', fontWeight: 600, color: '#1e293b' }}>
                Revision #{comparison.target_revision.revision_number}{' '}
                <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                  v{comparison.target_revision.quote_version}
                </span>
              </h3>
              <dl className="info-list" style={{ fontSize: '0.8125rem' }}>
                <dt>Captured By</dt>
                <dd>
                  {comparison.target_revision.user_email || `User #${comparison.target_revision.user_id}`}
                  {comparison.target_revision.user_role && ` (${comparison.target_revision.user_role})`}
                </dd>
                <dt>Date & Time</dt>
                <dd>{formatRevisionDate(comparison.target_revision.created_at)}</dd>
                {comparison.target_revision.change_reason && (
                  <>
                    <dt>Reason</dt>
                    <dd style={{ fontStyle: 'italic', color: '#475569' }}>
                      "{comparison.target_revision.change_reason}"
                    </dd>
                  </>
                )}
              </dl>
            </div>
          </div>

          {/* OVERALL CHANGE STATUS BANNER */}
          <div
            style={{
              padding: '0.875rem 1.25rem',
              borderRadius: '0.375rem',
              marginBottom: '1.5rem',
              backgroundColor: comparison.has_changes ? '#fef3c7' : '#f0fdf4',
              border: `1px solid ${comparison.has_changes ? '#fde68a' : '#bbf7d0'}`,
              color: comparison.has_changes ? '#92400e' : '#166534',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
            }}
          >
            <span style={{ fontSize: '1.25rem' }}>{comparison.has_changes ? '⚠️' : '✅'}</span>
            <div>
              <strong>
                {comparison.has_changes
                  ? `Changes Detected between Revision #${comparison.base_revision.revision_number} and Revision #${comparison.target_revision.revision_number}`
                  : `Identical Revisions: No changes between Revision #${comparison.base_revision.revision_number} and Revision #${comparison.target_revision.revision_number}`}
              </strong>
              <div style={{ fontSize: '0.8125rem', marginTop: '0.2rem' }}>
                {comparison.has_changes
                  ? `Differences include ${comparison.line_items.total_added} added, ${comparison.line_items.total_removed} removed, and ${comparison.line_items.total_modified} modified line items.`
                  : 'All metadata, requirements, commercials, and line items match exactly.'}
              </div>
            </div>
          </div>

          {/* 1. METADATA & CUSTOMER DETAIL DIFFERENCES */}
          <div className="card mb-4" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header" style={{ padding: '0.75rem 1.25rem', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: '#334155' }}>
                Quote Metadata & Customer Details
              </h3>
            </div>
            {comparison.metadata_changes && Object.keys(comparison.metadata_changes).length > 0 ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '30%' }}>Field</th>
                      <th style={{ width: '35%' }}>Base (Rev #{comparison.base_revision.revision_number})</th>
                      <th style={{ width: '35%' }}>Target (Rev #{comparison.target_revision.revision_number})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(comparison.metadata_changes).map(([field, diff]) => (
                      <tr key={`meta-${field}`}>
                        <td className="font-medium text-gray-900" style={{ textTransform: 'capitalize' }}>
                          {field.replace(/_/g, ' ')}
                        </td>
                        <td className="text-gray-600" style={{ backgroundColor: '#fff1f2' }}>
                          {formatFieldDiffValue(diff.old)}
                        </td>
                        <td className="font-semibold text-gray-900" style={{ backgroundColor: '#f0fdf4' }}>
                          {formatFieldDiffValue(diff.new)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '1rem 1.25rem', color: '#64748b', fontSize: '0.875rem', fontStyle: 'italic' }}>
                No metadata or customer detail changes between Revision #{comparison.base_revision.revision_number} and Revision #{comparison.target_revision.revision_number}.
              </div>
            )}
          </div>

          {/* 2. REQUIREMENTS DIFFERENCES */}
          <div className="card mb-4" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header" style={{ padding: '0.75rem 1.25rem', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: '#334155' }}>
                Scope & Requirements Differences
              </h3>
            </div>
            {comparison.requirement_changes && Object.keys(comparison.requirement_changes).length > 0 ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '30%' }}>Requirement</th>
                      <th style={{ width: '35%' }}>Base (Rev #{comparison.base_revision.revision_number})</th>
                      <th style={{ width: '35%' }}>Target (Rev #{comparison.target_revision.revision_number})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(comparison.requirement_changes).map(([field, diff]) => (
                      <tr key={`req-${field}`}>
                        <td className="font-medium text-gray-900" style={{ textTransform: 'capitalize' }}>
                          {field.replace(/_/g, ' ')}
                        </td>
                        <td className="text-gray-600" style={{ backgroundColor: '#fff1f2' }}>
                          {formatFieldDiffValue(diff.old)}
                        </td>
                        <td className="font-semibold text-gray-900" style={{ backgroundColor: '#f0fdf4' }}>
                          {formatFieldDiffValue(diff.new)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '1rem 1.25rem', color: '#64748b', fontSize: '0.875rem', fontStyle: 'italic' }}>
                No scope or requirements differences between Revision #{comparison.base_revision.revision_number} and Revision #{comparison.target_revision.revision_number}.
              </div>
            )}
          </div>

          {/* 3. COMMERCIAL & FINANCIAL DIFFERENCES */}
          <div className="card mb-4" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header" style={{ padding: '0.75rem 1.25rem', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: '#334155' }}>
                Commercial & Financial Differences
              </h3>
            </div>
            {Object.keys(safeFinancialChanges).length > 0 ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '30%' }}>Metric</th>
                      <th style={{ width: '35%' }}>Base (Rev #{comparison.base_revision.revision_number})</th>
                      <th style={{ width: '35%' }}>Target (Rev #{comparison.target_revision.revision_number})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(safeFinancialChanges).map(([field, diff]) => (
                      <tr key={`fin-${field}`}>
                        <td className="font-medium text-gray-900" style={{ textTransform: 'capitalize' }}>
                          {field.replace(/_/g, ' ')}
                        </td>
                        <td className="text-gray-600" style={{ backgroundColor: '#fff1f2' }}>
                          {formatFieldDiffValue(diff.old)}
                        </td>
                        <td className="font-semibold text-gray-900" style={{ backgroundColor: '#f0fdf4' }}>
                          {formatFieldDiffValue(diff.new)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '1rem 1.25rem', color: '#64748b', fontSize: '0.875rem', fontStyle: 'italic' }}>
                No commercial or financial differences between Revision #{comparison.base_revision.revision_number} and Revision #{comparison.target_revision.revision_number}.
              </div>
            )}
          </div>

          {/* 4. LEGAL ENTITY DIFFERENCES */}
          <div className="card mb-4" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header" style={{ padding: '0.75rem 1.25rem', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: '#334155' }}>
                Legal Entity Differences
              </h3>
            </div>
            {comparison.legal_entity_changes && Object.keys(comparison.legal_entity_changes).length > 0 ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '30%' }}>Attribute</th>
                      <th style={{ width: '35%' }}>Base (Rev #{comparison.base_revision.revision_number})</th>
                      <th style={{ width: '35%' }}>Target (Rev #{comparison.target_revision.revision_number})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(comparison.legal_entity_changes).map(([field, diff]) => (
                      <tr key={`legal-${field}`}>
                        <td className="font-medium text-gray-900" style={{ textTransform: 'capitalize' }}>
                          {field.replace(/_/g, ' ')}
                        </td>
                        <td className="text-gray-600" style={{ backgroundColor: '#fff1f2' }}>
                          {formatFieldDiffValue(diff.old)}
                        </td>
                        <td className="font-semibold text-gray-900" style={{ backgroundColor: '#f0fdf4' }}>
                          {formatFieldDiffValue(diff.new)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '1rem 1.25rem', color: '#64748b', fontSize: '0.875rem', fontStyle: 'italic' }}>
                No legal entity differences between Revision #{comparison.base_revision.revision_number} and Revision #{comparison.target_revision.revision_number}.
              </div>
            )}
          </div>

          {/* 5. BILL OF QUANTITIES LINE ITEM DIFFERENCES */}
          <div className="card mb-4" style={{ marginBottom: '2rem' }}>
            <div
              className="card-header"
              style={{
                padding: '0.75rem 1.25rem',
                backgroundColor: '#f8fafc',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '0.5rem',
              }}
            >
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: '#334155' }}>
                Line Item Differences
              </h3>

              {/* TABS / FILTERS */}
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('all')}
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  All Items ({comparison.line_items.total_added + comparison.line_items.total_removed + comparison.line_items.total_modified + comparison.line_items.total_unchanged})
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'added' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('added')}
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  + Added ({comparison.line_items.total_added})
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'removed' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('removed')}
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  - Removed ({comparison.line_items.total_removed})
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'modified' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('modified')}
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  Δ Modified ({comparison.line_items.total_modified})
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${activeTab === 'unchanged' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab('unchanged')}
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                >
                  = Unchanged ({comparison.line_items.total_unchanged})
                </button>
              </div>
            </div>

            {/* LINE ITEMS TABLE */}
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '12%' }}>Status</th>
                    <th style={{ width: '15%' }}>Part Number</th>
                    <th style={{ width: userHasCostVisibility ? '25%' : '35%' }}>Description & Section</th>
                    <th style={{ width: '10%', textAlign: 'center' }}>Quantity</th>
                    <th style={{ width: '14%', textAlign: 'right' }}>Unit Sell</th>
                    <th style={{ width: '14%', textAlign: 'right' }}>Line Total</th>
                    {userHasCostVisibility && (
                      <>
                        <th style={{ width: '12%', textAlign: 'right' }}>Unit Cost</th>
                        <th style={{ width: '12%', textAlign: 'right' }}>Margin %</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const itemsToDisplay = [];
                    if (activeTab === 'all' || activeTab === 'added') {
                      comparison.line_items.added.forEach((it) => itemsToDisplay.push(it));
                    }
                    if (activeTab === 'all' || activeTab === 'removed') {
                      comparison.line_items.removed.forEach((it) => itemsToDisplay.push(it));
                    }
                    if (activeTab === 'all' || activeTab === 'modified') {
                      comparison.line_items.modified.forEach((it) => itemsToDisplay.push(it));
                    }
                    if (activeTab === 'all' || activeTab === 'unchanged') {
                      comparison.line_items.unchanged.forEach((it) => itemsToDisplay.push(it));
                    }

                    if (itemsToDisplay.length === 0) {
                      return (
                        <tr>
                          <td colSpan={userHasCostVisibility ? 8 : 6} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                            No line items in category "{activeTab}".
                          </td>
                        </tr>
                      );
                    }

                    return itemsToDisplay.map((item, idx) => {
                      const badge = getLineItemCategoryBadge(item.status);
                      const isModified = item.status === 'modified';
                      const isAdded = item.status === 'added';
                      const isRemoved = item.status === 'removed';

                      return (
                        <tr
                          key={`${item.status}-${item.part_number || idx}-${idx}`}
                          style={{
                            backgroundColor: isAdded
                              ? '#f0fdf4'
                              : isRemoved
                              ? '#fff1f2'
                              : isModified
                              ? '#fefce8'
                              : 'inherit',
                          }}
                        >
                          {/* STATUS WITH ACCESSIBLE TEXT BADGE AND SYMBOL */}
                          <td>
                            <span className={`badge ${badge.className}`} style={{ fontSize: '0.7rem' }}>
                              {badge.label}
                            </span>
                          </td>

                          {/* PART NUMBER & BRAND */}
                          <td>
                            <div className="font-medium text-gray-900">{item.part_number || 'Custom'}</div>
                            {item.brand && <div className="text-xs text-gray-500">{item.brand}</div>}
                          </td>

                          {/* DESCRIPTION & SECTION */}
                          <td>
                            <div className="text-sm text-gray-900">{item.description}</div>
                            {item.section && <div className="text-xs text-gray-500">[{item.section}]</div>}
                          </td>

                          {/* QUANTITY */}
                          <td style={{ textAlign: 'center' }}>
                            {isModified && item.quantity_old !== item.quantity_new ? (
                              <div>
                                <span style={{ textDecoration: 'line-through', color: '#dc2626', marginRight: '0.25rem' }}>
                                  {item.quantity_old}
                                </span>
                                <span style={{ color: '#16a34a', fontWeight: 600 }}>
                                  → {item.quantity_new}
                                </span>
                              </div>
                            ) : isAdded ? (
                              <span style={{ color: '#16a34a', fontWeight: 600 }}>{item.quantity_new}</span>
                            ) : isRemoved ? (
                              <span style={{ textDecoration: 'line-through', color: '#dc2626' }}>{item.quantity_old}</span>
                            ) : (
                              <span>{item.quantity_new}</span>
                            )}
                          </td>

                          {/* UNIT SELL PRICE */}
                          <td style={{ textAlign: 'right' }}>
                            {isModified && item.unit_sell_price_old !== item.unit_sell_price_new ? (
                              <div>
                                <div style={{ textDecoration: 'line-through', color: '#dc2626', fontSize: '0.8125rem' }}>
                                  {formatSnapshotUsd(item.unit_sell_price_old)}
                                </div>
                                <div style={{ color: '#16a34a', fontWeight: 600, fontSize: '0.8125rem' }}>
                                  {formatSnapshotUsd(item.unit_sell_price_new)}
                                </div>
                              </div>
                            ) : isAdded ? (
                              <span style={{ color: '#16a34a', fontWeight: 600 }}>
                                {formatSnapshotUsd(item.unit_sell_price_new)}
                              </span>
                            ) : isRemoved ? (
                              <span style={{ textDecoration: 'line-through', color: '#dc2626' }}>
                                {formatSnapshotUsd(item.unit_sell_price_old)}
                              </span>
                            ) : (
                              <span>{formatSnapshotUsd(item.unit_sell_price_new)}</span>
                            )}
                          </td>

                          {/* LINE SELL TOTAL */}
                          <td style={{ textAlign: 'right' }}>
                            {isModified && item.line_sell_total_old !== item.line_sell_total_new ? (
                              <div>
                                <div style={{ textDecoration: 'line-through', color: '#dc2626', fontSize: '0.8125rem' }}>
                                  {formatSnapshotUsd(item.line_sell_total_old)}
                                </div>
                                <div style={{ color: '#16a34a', fontWeight: 600, fontSize: '0.8125rem' }}>
                                  {formatSnapshotUsd(item.line_sell_total_new)}
                                </div>
                              </div>
                            ) : isAdded ? (
                              <span style={{ color: '#16a34a', fontWeight: 600 }}>
                                {formatSnapshotUsd(item.line_sell_total_new)}
                              </span>
                            ) : isRemoved ? (
                              <span style={{ textDecoration: 'line-through', color: '#dc2626' }}>
                                {formatSnapshotUsd(item.line_sell_total_old)}
                              </span>
                            ) : (
                              <span>{formatSnapshotUsd(item.line_sell_total_new)}</span>
                            )}
                          </td>

                          {/* UNIT COST PRICE (STRICTLY AUTHORIZED) */}
                          {userHasCostVisibility && (
                            <>
                              <td style={{ textAlign: 'right' }}>
                                {isModified && item.unit_cost_price_old !== item.unit_cost_price_new ? (
                                  <div>
                                    <div style={{ textDecoration: 'line-through', color: '#dc2626', fontSize: '0.8125rem' }}>
                                      {formatSnapshotUsd(item.unit_cost_price_old)}
                                    </div>
                                    <div style={{ color: '#16a34a', fontWeight: 600, fontSize: '0.8125rem' }}>
                                      {formatSnapshotUsd(item.unit_cost_price_new)}
                                    </div>
                                  </div>
                                ) : isAdded ? (
                                  <span style={{ color: '#16a34a', fontWeight: 600 }}>
                                    {formatSnapshotUsd(item.unit_cost_price_new)}
                                  </span>
                                ) : isRemoved ? (
                                  <span style={{ textDecoration: 'line-through', color: '#dc2626' }}>
                                    {formatSnapshotUsd(item.unit_cost_price_old)}
                                  </span>
                                ) : (
                                  <span>{formatSnapshotUsd(item.unit_cost_price_new)}</span>
                                )}
                              </td>

                              {/* MARGIN % (STRICTLY AUTHORIZED) */}
                              <td style={{ textAlign: 'right' }}>
                                {isModified && item.margin_percent_old !== item.margin_percent_new ? (
                                  <div>
                                    <div style={{ textDecoration: 'line-through', color: '#dc2626', fontSize: '0.8125rem' }}>
                                      {formatSnapshotPercent(item.margin_percent_old)}
                                    </div>
                                    <div style={{ color: '#16a34a', fontWeight: 600, fontSize: '0.8125rem' }}>
                                      {formatSnapshotPercent(item.margin_percent_new)}
                                    </div>
                                  </div>
                                ) : isAdded ? (
                                  <span style={{ color: '#16a34a', fontWeight: 600 }}>
                                    {formatSnapshotPercent(item.margin_percent_new)}
                                  </span>
                                ) : isRemoved ? (
                                  <span style={{ textDecoration: 'line-through', color: '#dc2626' }}>
                                    {formatSnapshotPercent(item.margin_percent_old)}
                                  </span>
                                ) : (
                                  <span>{formatSnapshotPercent(item.margin_percent_new)}</span>
                                )}
                              </td>
                            </>
                          )}
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {/* FOOTER ACTION BAR */}
      <div className="preview-actions" style={{ marginTop: '2rem' }}>
        <div className="action-left">
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={() => navigate(`/quotes/${id}`)}
          >
            &larr; Back to Current Quote Details
          </button>
        </div>
        <div className="action-right" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {baseRevNum && (
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={() => navigate(getSnapshotViewUrl(id, baseRevNum))}
            >
              View Base Rev #{baseRevNum} Snapshot
            </button>
          )}
          {targetRevNum && (
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={() => navigate(getSnapshotViewUrl(id, targetRevNum))}
            >
              View Target Rev #{targetRevNum} Snapshot
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
