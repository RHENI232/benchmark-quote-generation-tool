/**
 * Revision history formatting and presentation utilities.
 * Pure JavaScript functions compatible with both React components and Node.js testing.
 */

/**
 * Maps revision action types to semantic CSS badge classes.
 */
export function getActionBadgeClass(action) {
  switch (action) {
    case 'APPROVE':
    case 'OVERRIDE_APPROVE':
      return 'badge-success';
    case 'REQUEST_CHANGES':
      return 'badge-danger';
    case 'INITIAL_CREATION':
    case 'SUBMIT':
      return 'badge-info';
    case 'EDIT':
    case 'RECALCULATE':
    case 'FX_REFRESH':
      return 'badge-warning';
    default:
      return 'badge-neutral';
  }
}

/**
 * Formats an action string for human-readable display.
 */
export function formatActionLabel(action) {
  if (!action) return 'UNKNOWN';
  return action.replace(/_/g, ' ');
}

/**
 * Formats an ISO datetime string for consistent display.
 */
export function formatRevisionDate(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

/**
 * Formats an amount into a localized currency string.
 */
export function formatSnapshotMoney(amount, currencyCode = 'USD') {
  if (amount == null) return '—';
  const num = parseFloat(amount);
  if (isNaN(num)) return String(amount);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode || 'USD',
  }).format(num);
}

/**
 * Formats an amount into USD currency string.
 */
export function formatSnapshotUsd(amount) {
  if (amount == null) return '—';
  const num = parseFloat(amount);
  if (isNaN(num)) return String(amount);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num);
}

/**
 * Formats a percentage value (e.g. 25.5 -> 25.5%).
 */
export function formatSnapshotPercent(amount) {
  if (amount == null) return '—';
  const num = parseFloat(amount);
  if (isNaN(num)) return String(amount);
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(num / 100);
}

/**
 * Groups snapshot line items by section.
 */
export function groupSnapshotLineItems(lineItems = []) {
  const grouped = {};
  if (!Array.isArray(lineItems)) return grouped;

  lineItems.forEach((item) => {
    const sec = item.section || 'General';
    if (!grouped[sec]) grouped[sec] = [];
    grouped[sec].push(item);
  });
  return grouped;
}

/**
 * Evaluates whether sensitive cost/margin fields can be displayed.
 * Both the data must be unmasked (non-null) AND the user must possess cost visibility.
 */
export function canDisplayCostData(financials, userHasCostVisibility = false) {
  if (!userHasCostVisibility) return false;
  if (!financials) return false;
  return financials.subtotal_cost_usd !== null && financials.subtotal_cost_usd !== undefined;
}

/**
 * Constructs the query string for getQuoteRevisions API requests.
 */
export function buildRevisionsQueryString({ skip = 0, limit = 50, order = 'asc' } = {}) {
  const params = new URLSearchParams();
  if (skip !== undefined && skip !== null) params.append('skip', skip);
  if (limit !== undefined && limit !== null) params.append('limit', limit);
  if (order) params.append('order', order);
  return params.toString();
}

/**
 * Generates the target navigation URL for viewing a historical snapshot.
 */
export function getSnapshotViewUrl(quoteId, revisionNumber) {
  return `/quotes/${quoteId}/revisions/${revisionNumber}`;
}

/**
 * Generates the target navigation URL for comparing two historical revisions.
 * Follows the standard route pattern /quotes/:id/revisions/compare?from=X&to=Y.
 */
export function buildComparisonUrl(quoteId, fromRevision, toRevision) {
  const params = new URLSearchParams();
  if (fromRevision !== undefined && fromRevision !== null) params.append('from', fromRevision);
  if (toRevision !== undefined && toRevision !== null) params.append('to', toRevision);
  const q = params.toString();
  return `/quotes/${quoteId}/revisions/compare${q ? `?${q}` : ''}`;
}

/**
 * Validates revision parameters for comparison.
 * Ensures both parameters are positive integers and distinct.
 */
export function validateComparisonParams(fromVal, toVal) {
  const isFromEmpty = fromVal === null || fromVal === undefined || String(fromVal).trim() === '';
  const isToEmpty = toVal === null || toVal === undefined || String(toVal).trim() === '';

  if (isFromEmpty || isToEmpty) {
    return {
      isValid: false,
      isMissing: true,
      isDistinctError: false,
      from: null,
      to: null,
      error: 'Please select both a base and target revision to compare.',
    };
  }

  const fromStr = String(fromVal).trim();
  const toStr = String(toVal).trim();
  const fromNum = Number(fromStr);
  const toNum = Number(toStr);

  if (!Number.isInteger(fromNum) || fromNum < 1 || String(fromNum) !== fromStr) {
    return {
      isValid: false,
      isMissing: false,
      isDistinctError: false,
      from: null,
      to: null,
      error: "The 'from' revision parameter must be a positive integer.",
    };
  }

  if (!Number.isInteger(toNum) || toNum < 1 || String(toNum) !== toStr) {
    return {
      isValid: false,
      isMissing: false,
      isDistinctError: false,
      from: null,
      to: null,
      error: "The 'to' revision parameter must be a positive integer.",
    };
  }

  if (fromNum === toNum) {
    return {
      isValid: false,
      isMissing: false,
      isDistinctError: true,
      from: fromNum,
      to: toNum,
      error: 'Base and target revisions must be distinct. Please select two different revisions to compare.',
    };
  }

  return {
    isValid: true,
    isMissing: false,
    isDistinctError: false,
    from: fromNum,
    to: toNum,
    error: null,
  };
}

/**
 * Checks whether a field name pertains to restricted cost or margin data.
 */
export function isCostOrMarginField(fieldName) {
  if (!fieldName || typeof fieldName !== 'string') return false;
  const lower = fieldName.toLowerCase();
  return (
    lower.includes('cost') ||
    lower.includes('margin') ||
    lower === 'unit_cost_price_snapshot' ||
    lower === 'line_cost_total' ||
    lower === 'subtotal_cost_usd'
  );
}

/**
 * Filters financial field differences to exclude cost/margin fields if caller lacks permission.
 */
export function filterFinancialChanges(financialChanges = {}, userHasCostVisibility = false) {
  if (!financialChanges || typeof financialChanges !== 'object') return {};
  const filtered = {};
  for (const [key, diff] of Object.entries(financialChanges)) {
    if (isCostOrMarginField(key) && !userHasCostVisibility) {
      continue;
    }
    filtered[key] = diff;
  }
  return filtered;
}

/**
 * Swaps two revision numbers and returns an updated pair.
 */
export function swapRevisionNumbers(from, to) {
  return { from: to, to: from };
}

/**
 * Classifies revision comparison API errors into user-actionable messages.
 */
export function classifyComparisonError(err, baseNum, targetNum) {
  if (!err) return 'An unexpected error occurred during revision comparison.';

  if (
    err.status === 401 ||
    err.message?.toLowerCase().includes('token has expired') ||
    err.message?.toLowerCase().includes('not authenticated')
  ) {
    return 'Your session has expired or you are not signed in. Please sign in again.';
  }

  if (err.status === 403) {
    return 'You do not have permission to compare revisions for this quote.';
  }

  if (err.status === 404) {
    if (baseNum && targetNum) {
      return `One or both revisions (#${baseNum}, #${targetNum}) were not found for this quote.`;
    }
    return 'The requested quote or revision was not found.';
  }

  if (err.status >= 500) {
    return 'The server encountered an error while calculating revision differences. Please try again later.';
  }

  return err.message || 'Failed to compare historical revisions.';
}

/**
 * Returns accessible badge metadata and symbol for a line item delta category.
 */
export function getLineItemCategoryBadge(status) {
  switch (status) {
    case 'added':
      return { label: '+ ADDED', className: 'badge-success', symbol: '+' };
    case 'removed':
      return { label: '- REMOVED', className: 'badge-danger', symbol: '-' };
    case 'modified':
      return { label: 'Δ MODIFIED', className: 'badge-warning', symbol: 'Δ' };
    case 'unchanged':
    default:
      return { label: '= UNCHANGED', className: 'badge-neutral', symbol: '=' };
  }
}

/**
 * Formats old/new primitive values in field-level diffs for display.
 */
export function formatFieldDiffValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

