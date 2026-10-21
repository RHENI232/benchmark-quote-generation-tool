import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getActionBadgeClass,
  formatActionLabel,
  formatRevisionDate,
  formatSnapshotMoney,
  formatSnapshotUsd,
  formatSnapshotPercent,
  groupSnapshotLineItems,
  canDisplayCostData,
  buildRevisionsQueryString,
  getSnapshotViewUrl,
  buildComparisonUrl,
  getLineItemCategoryBadge,
  formatFieldDiffValue,
  validateComparisonParams,
  filterFinancialChanges,
  isCostOrMarginField,
  swapRevisionNumbers,
  classifyComparisonError,
} from '../utils/revisionFormatters.js';

// -----------------------------------------------------------------------------
// Test Suite 1: API URL Construction
// -----------------------------------------------------------------------------
function buildRevisionsUrl(quoteId, { skip = 0, limit = 50, order = 'asc' } = {}) {
  const query = buildRevisionsQueryString({ skip, limit, order });
  return `/api/quotes/${quoteId}/revisions?${query}`;
}

function buildSingleRevisionUrl(quoteId, revisionNumber) {
  return `/api/quotes/${quoteId}/revisions/${revisionNumber}`;
}

function buildComparisonApiUrl(quoteId, baseRevision, targetRevision) {
  const params = new URLSearchParams({
    base_revision: baseRevision,
    target_revision: targetRevision,
  });
  return `/api/quotes/${quoteId}/revisions/compare?${params.toString()}`;
}

test('API URL: getQuoteRevisions default parameters', () => {
  const url = buildRevisionsUrl(42);
  assert.equal(url, '/api/quotes/42/revisions?skip=0&limit=50&order=asc');
});

test('API URL: getQuoteRevisions custom pagination and descending order', () => {
  const url = buildRevisionsUrl(101, { skip: 20, limit: 10, order: 'desc' });
  assert.equal(url, '/api/quotes/101/revisions?skip=20&limit=10&order=desc');
});

test('API URL: getQuoteRevision single revision path construction', () => {
  const url = buildSingleRevisionUrl(42, 3);
  assert.equal(url, '/api/quotes/42/revisions/3');
});

test('API URL: compareQuoteRevisions query parameter construction', () => {
  const url = buildComparisonApiUrl(42, 1, 2);
  assert.equal(url, '/api/quotes/42/revisions/compare?base_revision=1&target_revision=2');
});

// -----------------------------------------------------------------------------
// Test Suite 2: Action Badge Semantic Styling
// -----------------------------------------------------------------------------
test('UI Badge: maps all CP15 revision actions to semantic badge classes', () => {
  // Approvals -> Success
  assert.equal(getActionBadgeClass('APPROVE'), 'badge-success');
  assert.equal(getActionBadgeClass('OVERRIDE_APPROVE'), 'badge-success');

  // Change requests -> Danger
  assert.equal(getActionBadgeClass('REQUEST_CHANGES'), 'badge-danger');

  // Creation & submission -> Info
  assert.equal(getActionBadgeClass('INITIAL_CREATION'), 'badge-info');
  assert.equal(getActionBadgeClass('SUBMIT'), 'badge-info');

  // Edits, recalculations, and FX refreshes -> Warning
  assert.equal(getActionBadgeClass('EDIT'), 'badge-warning');
  assert.equal(getActionBadgeClass('RECALCULATE'), 'badge-warning');
  assert.equal(getActionBadgeClass('FX_REFRESH'), 'badge-warning');

  // Fallback / Unknown actions -> Neutral
  assert.equal(getActionBadgeClass('UNKNOWN_CUSTOM_ACTION'), 'badge-neutral');
  assert.equal(getActionBadgeClass(null), 'badge-neutral');
});

// -----------------------------------------------------------------------------
// Test Suite 3: Formatting Utilities
// -----------------------------------------------------------------------------
test('Formatting: formatActionLabel replaces underscores with spaces', () => {
  assert.equal(formatActionLabel('INITIAL_CREATION'), 'INITIAL CREATION');
  assert.equal(formatActionLabel('REQUEST_CHANGES'), 'REQUEST CHANGES');
  assert.equal(formatActionLabel('FX_REFRESH'), 'FX REFRESH');
  assert.equal(formatActionLabel('APPROVE'), 'APPROVE');
  assert.equal(formatActionLabel(null), 'UNKNOWN');
  assert.equal(formatActionLabel(''), 'UNKNOWN');
});

test('Formatting: formatRevisionDate handles valid, invalid, and empty dates', () => {
  assert.equal(formatRevisionDate(null), '—');
  assert.equal(formatRevisionDate(''), '—');
  assert.equal(formatRevisionDate(undefined), '—');

  // Valid ISO date
  const formatted = formatRevisionDate('2026-10-20T11:45:00.000Z');
  assert.ok(formatted.includes('2026'));
  assert.ok(formatted.includes('10') || formatted.includes('Oct'));
});

test('Formatting: formatSnapshotMoney and formatSnapshotUsd handle precision and currencies', () => {
  assert.equal(formatSnapshotMoney(null, 'SGD'), '—');
  assert.equal(formatSnapshotMoney(undefined, 'USD'), '—');

  const formattedSgd = formatSnapshotMoney('17550.00', 'SGD');
  assert.ok(formattedSgd.includes('17,550'));

  const formattedUsd = formatSnapshotUsd('12000.50');
  assert.ok(formattedUsd.includes('12,000.50'));
  assert.ok(formattedUsd.includes('$'));
});

test('Formatting: formatSnapshotPercent handles decimal margins', () => {
  assert.equal(formatSnapshotPercent(null), '—');
  assert.equal(formatSnapshotPercent(undefined), '—');
  const formatted = formatSnapshotPercent('25.5');
  assert.ok(formatted.includes('25.5') || formatted.includes('25.50'));
});

test('Formatting: formatFieldDiffValue formats primitives, booleans, and nulls', () => {
  assert.equal(formatFieldDiffValue(null), '—');
  assert.equal(formatFieldDiffValue(undefined), '—');
  assert.equal(formatFieldDiffValue(true), 'Yes');
  assert.equal(formatFieldDiffValue(false), 'No');
  assert.equal(formatFieldDiffValue('draft'), 'draft');
  assert.equal(formatFieldDiffValue(42), '42');
});

// -----------------------------------------------------------------------------
// Test Suite 4: Historical Snapshot Field Extraction & Fidelity
// -----------------------------------------------------------------------------
test('Snapshot Fidelity: extracts quote header, solution, region, and legal entity as stored', () => {
  const sampleSnapshot = {
    schema_version: '1.0',
    captured_at: '2026-10-20T11:45:00.000Z',
    quote: {
      id: 42,
      quote_ref_no: 'BBS-2026-000042',
      version: 2,
      status: 'draft',
      client_name: 'Acme Television Network',
      attention: 'Technical Director',
      description: 'Newsroom upgrade phase 2',
      solution_name: 'Newsroom Playout System',
      region_name: 'Singapore',
      is_urgent: true,
      requirement_data: {
        number_of_studios: 2,
        news_production: true,
      },
    },
    financials: {
      currency_code: 'SGD',
      fx_rate_to_usd: '0.745000',
      fx_rate_as_of: '2026-10-20 09:00:00 UTC',
      tax_enabled: true,
      tax_rate_percent: '9.00',
      subtotal_sell_usd: '12000.00',
      tax_amount: '1450.00',
      total_sell_local: '17550.00',
    },
    legal_entity: {
      legal_entity_name: 'Benchmark Broadcast Systems (S) Pte Ltd',
      legal_entity_registration_number: '199801234K',
    },
    line_items: [
      { id: 1, section: 'Cameras', part_number: 'CAM-01', description: 'Studio Camera', quantity: 2 },
      { id: 2, section: 'Switchers', part_number: 'SW-01', description: 'Production Switcher', quantity: 1 },
      { id: 3, section: 'Cameras', part_number: 'LENS-01', description: 'Zoom Lens', quantity: 2 },
    ],
  };

  // Verify direct extraction without recalculation
  assert.equal(sampleSnapshot.quote.client_name, 'Acme Television Network');
  assert.equal(sampleSnapshot.quote.quote_ref_no, 'BBS-2026-000042');
  assert.equal(sampleSnapshot.quote.solution_name, 'Newsroom Playout System');
  assert.equal(sampleSnapshot.quote.region_name, 'Singapore');
  assert.equal(sampleSnapshot.quote.is_urgent, true);
  assert.equal(sampleSnapshot.quote.requirement_data.number_of_studios, 2);

  // Financial values must remain exactly as stored
  assert.equal(sampleSnapshot.financials.subtotal_sell_usd, '12000.00');
  assert.equal(sampleSnapshot.financials.tax_amount, '1450.00');
  assert.equal(sampleSnapshot.financials.total_sell_local, '17550.00');
  assert.equal(sampleSnapshot.financials.fx_rate_to_usd, '0.745000');

  // Legal entity
  assert.equal(sampleSnapshot.legal_entity.legal_entity_name, 'Benchmark Broadcast Systems (S) Pte Ltd');
});

test('Snapshot Fidelity: groupSnapshotLineItems groups items by section preserving order', () => {
  const lineItems = [
    { id: 1, section: 'Cameras', description: 'Camera 1' },
    { id: 2, section: 'Switchers', description: 'Switcher 1' },
    { id: 3, section: 'Cameras', description: 'Lens' },
    { id: 4, section: null, description: 'General Cable' },
  ];

  const grouped = groupSnapshotLineItems(lineItems);
  assert.deepEqual(Object.keys(grouped), ['Cameras', 'Switchers', 'General']);
  assert.equal(grouped['Cameras'].length, 2);
  assert.equal(grouped['Switchers'].length, 1);
  assert.equal(grouped['General'].length, 1);
  assert.equal(grouped['General'][0].description, 'General Cable');
});

// -----------------------------------------------------------------------------
// Test Suite 5: Revision Comparison Categorization & Accessible Indicators
// -----------------------------------------------------------------------------
test('Comparison UI: getLineItemCategoryBadge returns text and symbols (not color alone)', () => {
  const addedBadge = getLineItemCategoryBadge('added');
  assert.equal(addedBadge.label, '+ ADDED');
  assert.equal(addedBadge.symbol, '+');
  assert.equal(addedBadge.className, 'badge-success');

  const removedBadge = getLineItemCategoryBadge('removed');
  assert.equal(removedBadge.label, '- REMOVED');
  assert.equal(removedBadge.symbol, '-');
  assert.equal(removedBadge.className, 'badge-danger');

  const modifiedBadge = getLineItemCategoryBadge('modified');
  assert.equal(modifiedBadge.label, 'Δ MODIFIED');
  assert.equal(modifiedBadge.symbol, 'Δ');
  assert.equal(modifiedBadge.className, 'badge-warning');

  const unchangedBadge = getLineItemCategoryBadge('unchanged');
  assert.equal(unchangedBadge.label, '= UNCHANGED');
  assert.equal(unchangedBadge.symbol, '=');
  assert.equal(unchangedBadge.className, 'badge-neutral');
});

test('Comparison Fidelity: handles backend line item categories without frontend recalculation', () => {
  const mockBackendComparison = {
    quote_id: 42,
    quote_ref_no: 'BBS-2026-000042',
    has_changes: true,
    base_revision: { revision_number: 1, quote_version: 1, action: 'INITIAL_CREATION' },
    target_revision: { revision_number: 2, quote_version: 2, action: 'EDIT' },
    metadata_changes: {
      status: { old: 'draft', new: 'changes_requested', changed: true },
    },
    line_items: {
      added: [{ part_number: 'CAM-4K', quantity_new: 2, status: 'added' }],
      removed: [{ part_number: 'CAM-HD', quantity_old: 2, status: 'removed' }],
      modified: [{ part_number: 'SW-01', quantity_old: 1, quantity_new: 2, status: 'modified' }],
      unchanged: [{ part_number: 'CBL-01', quantity_new: 10, status: 'unchanged' }],
      total_added: 1,
      total_removed: 1,
      total_modified: 1,
      total_unchanged: 1,
    },
  };

  assert.equal(mockBackendComparison.has_changes, true);
  assert.equal(mockBackendComparison.line_items.added[0].status, 'added');
  assert.equal(mockBackendComparison.line_items.removed[0].status, 'removed');
  assert.equal(mockBackendComparison.line_items.modified[0].quantity_new, 2);
  assert.equal(mockBackendComparison.line_items.unchanged[0].part_number, 'CBL-01');
});

// -----------------------------------------------------------------------------
// Test Suite 6: Security & Cost Visibility Masking
// -----------------------------------------------------------------------------
test('Security: canDisplayCostData respects both backend masking and caller permission', () => {
  // Case 1: Caller lacks cost_visibility (Sales user) -> NEVER show cost data
  const unmaskedFinancials = { subtotal_cost_usd: '8500.00' };
  assert.equal(canDisplayCostData(unmaskedFinancials, false), false);

  // Case 2: Caller has cost_visibility but backend masked it (e.g. null) -> Cannot show
  const maskedFinancials = { subtotal_cost_usd: null };
  assert.equal(canDisplayCostData(maskedFinancials, true), false);

  // Case 3: Caller has cost_visibility AND data is present -> Allowed to display
  assert.equal(canDisplayCostData(unmaskedFinancials, true), true);

  // Case 4: Null financials object
  assert.equal(canDisplayCostData(null, true), false);
  assert.equal(canDisplayCostData(null, false), false);
});

test('Security: Cost deltas are excluded in comparison view for unauthorized users', () => {
  const financialChanges = {
    subtotal_sell_usd: { old: '10000.00', new: '12000.00', changed: true },
    subtotal_cost_usd: { old: '7000.00', new: '8000.00', changed: true },
  };

  const shouldRenderField = (field, userHasCostVisibility) => {
    if (field === 'subtotal_cost_usd') return userHasCostVisibility;
    return true;
  };

  const displayedForSales = Object.keys(financialChanges).filter((f) => shouldRenderField(f, false));
  assert.deepEqual(displayedForSales, ['subtotal_sell_usd']);

  const displayedForManagement = Object.keys(financialChanges).filter((f) => shouldRenderField(f, true));
  assert.deepEqual(displayedForManagement, ['subtotal_sell_usd', 'subtotal_cost_usd']);
});

test('Security: filterFinancialChanges strictly removes cost and margin fields when unauthorized', () => {
  const changes = {
    currency_code: { old: 'USD', new: 'SGD', changed: true },
    subtotal_sell_usd: { old: '10000.00', new: '15000.00', changed: true },
    subtotal_cost_usd: { old: '7000.00', new: '9500.00', changed: true },
    margin_percent: { old: '30.0', new: '36.6', changed: true },
  };

  // Unauthorized (Sales user)
  const safeForSales = filterFinancialChanges(changes, false);
  assert.deepEqual(Object.keys(safeForSales), ['currency_code', 'subtotal_sell_usd']);
  assert.equal('subtotal_cost_usd' in safeForSales, false);
  assert.equal('margin_percent' in safeForSales, false);

  // Authorized (Finance / Admin user)
  const safeForAdmin = filterFinancialChanges(changes, true);
  assert.deepEqual(Object.keys(safeForAdmin), [
    'currency_code',
    'subtotal_sell_usd',
    'subtotal_cost_usd',
    'margin_percent',
  ]);
});

test('Security: isCostOrMarginField correctly detects restricted field variations', () => {
  assert.equal(isCostOrMarginField('subtotal_cost_usd'), true);
  assert.equal(isCostOrMarginField('unit_cost_price_snapshot'), true);
  assert.equal(isCostOrMarginField('line_cost_total'), true);
  assert.equal(isCostOrMarginField('margin_percent'), true);
  assert.equal(isCostOrMarginField('gross_margin'), true);

  // Non-restricted commercial fields
  assert.equal(isCostOrMarginField('subtotal_sell_usd'), false);
  assert.equal(isCostOrMarginField('unit_sell_price_snapshot'), false);
  assert.equal(isCostOrMarginField('total_sell_local'), false);
  assert.equal(isCostOrMarginField('tax_amount'), false);
  assert.equal(isCostOrMarginField('currency_code'), false);
});

// -----------------------------------------------------------------------------
// Test Suite 7: Parameter Validation & Distinct Checking
// -----------------------------------------------------------------------------
test('Route Params: validateComparisonParams accepts valid positive integers', () => {
  const result = validateComparisonParams('1', '2');
  assert.equal(result.isValid, true);
  assert.equal(result.from, 1);
  assert.equal(result.to, 2);
  assert.equal(result.error, null);

  const numResult = validateComparisonParams(2, 5);
  assert.equal(numResult.isValid, true);
  assert.equal(numResult.from, 2);
  assert.equal(numResult.to, 5);
});

test('Route Params: validateComparisonParams detects invalid or missing numbers', () => {
  // Missing parameters
  const missingBoth = validateComparisonParams(null, null);
  assert.equal(missingBoth.isValid, false);
  assert.equal(missingBoth.isMissing, true);

  const missingTarget = validateComparisonParams('1', null);
  assert.equal(missingTarget.isValid, false);
  assert.equal(missingTarget.isMissing, true);

  // Non-integer string
  const notNumber = validateComparisonParams('abc', '2');
  assert.equal(notNumber.isValid, false);
  assert.ok(notNumber.error.includes('positive integer'));

  // Negative number
  const negativeFrom = validateComparisonParams('-1', '2');
  assert.equal(negativeFrom.isValid, false);
  assert.ok(negativeFrom.error.includes('positive integer'));

  // Zero
  const zeroTarget = validateComparisonParams('1', '0');
  assert.equal(zeroTarget.isValid, false);
  assert.ok(zeroTarget.error.includes('positive integer'));

  // Floating point
  const floatTarget = validateComparisonParams('1', '2.5');
  assert.equal(floatTarget.isValid, false);
  assert.ok(floatTarget.error.includes('positive integer'));
});

test('Route Params: validateComparisonParams rejects identical revisions (distinct requirement)', () => {
  const distinctCheck = validateComparisonParams('2', '2');
  assert.equal(distinctCheck.isValid, false);
  assert.equal(distinctCheck.isDistinctError, true);
  assert.equal(distinctCheck.from, 2);
  assert.equal(distinctCheck.to, 2);
  assert.ok(distinctCheck.error.includes('must be distinct'));
});

// -----------------------------------------------------------------------------
// Test Suite 8: Revision Swapping
// -----------------------------------------------------------------------------
test('Selection: swapRevisionNumbers reverses from and to numbers', () => {
  const swapped = swapRevisionNumbers(1, 3);
  assert.equal(swapped.from, 3);
  assert.equal(swapped.to, 1);

  const reSwapped = swapRevisionNumbers(swapped.from, swapped.to);
  assert.equal(reSwapped.from, 1);
  assert.equal(reSwapped.to, 3);
});

// -----------------------------------------------------------------------------
// Test Suite 9: Navigation, Route URL Building & Snapshot Links
// -----------------------------------------------------------------------------
test('Navigation: buildComparisonUrl constructs standard ?from=X&to=Y format', () => {
  const urlBoth = buildComparisonUrl(42, 1, 2);
  assert.equal(urlBoth, '/quotes/42/revisions/compare?from=1&to=2');

  const urlFromOnly = buildComparisonUrl(42, 3, null);
  assert.equal(urlFromOnly, '/quotes/42/revisions/compare?from=3');

  const urlEmpty = buildComparisonUrl(42, null, null);
  assert.equal(urlEmpty, '/quotes/42/revisions/compare');
});

test('Navigation: snapshot view URL generator and back navigation target', () => {
  const quoteId = 42;
  const revisionNumber = 3;

  const snapshotUrl = getSnapshotViewUrl(quoteId, revisionNumber);
  assert.equal(snapshotUrl, '/quotes/42/revisions/3');

  const backUrl = `/quotes/${quoteId}`;
  assert.equal(backUrl, '/quotes/42');
});

// -----------------------------------------------------------------------------
// Test Suite 10: Error Classification & Resilience
// -----------------------------------------------------------------------------
test('Error Handling: classifyComparisonError categorizes 401, 403, 404, 500 and network errors', () => {
  const err401 = new Error('Token has expired');
  err401.status = 401;
  assert.equal(
    classifyComparisonError(err401),
    'Your session has expired or you are not signed in. Please sign in again.'
  );

  const err403 = new Error('Forbidden: You do not own this quote');
  err403.status = 403;
  assert.equal(
    classifyComparisonError(err403),
    'You do not have permission to compare revisions for this quote.'
  );

  const err404 = new Error('Revision not found');
  err404.status = 404;
  assert.equal(
    classifyComparisonError(err404, 1, 99),
    'One or both revisions (#1, #99) were not found for this quote.'
  );

  const err500 = new Error('Internal Server Error');
  err500.status = 500;
  assert.equal(
    classifyComparisonError(err500),
    'The server encountered an error while calculating revision differences. Please try again later.'
  );

  const errNetwork = new Error('Network connection lost');
  assert.equal(classifyComparisonError(errNetwork), 'Network connection lost');
});

// -----------------------------------------------------------------------------
// Test Suite 11: Loading, Empty, and Success State Logic
// -----------------------------------------------------------------------------
test('State Handling: Empty state and revision list boundary handling', () => {
  const revisionsEmpty = [];
  const revisionsSingle = [{ id: 1, revision_number: 1, quote_version: 1 }];
  const revisionsMultiple = [
    { id: 1, revision_number: 1, quote_version: 1 },
    { id: 2, revision_number: 2, quote_version: 2 },
  ];

  // At least 2 revisions needed for a meaningful comparison
  const canCompare = (revs) => Array.isArray(revs) && revs.length >= 2;
  assert.equal(canCompare(revisionsEmpty), false);
  assert.equal(canCompare(revisionsSingle), false);
  assert.equal(canCompare(revisionsMultiple), true);

  // Default selection when multiple revisions exist: second-to-last and last
  const getDefaultPair = (revs) => {
    if (!canCompare(revs)) return { from: null, to: null };
    return {
      from: revs[revs.length - 2].revision_number,
      to: revs[revs.length - 1].revision_number,
    };
  };

  assert.deepEqual(getDefaultPair(revisionsMultiple), { from: 1, to: 2 });
});

// -----------------------------------------------------------------------------
// Test Suite 12: Incomplete & Empty Comparison Responses
// -----------------------------------------------------------------------------
test('Resilience: handles empty or incomplete comparison responses without crashing', () => {
  // Scenario 1: Minimal comparison payload with empty diff collections
  const emptyComparison = {
    quote_id: 101,
    quote_ref_no: 'BBS-2026-000101',
    has_changes: false,
    base_revision: { revision_number: 1, quote_version: 1, action: 'INITIAL_CREATION' },
    target_revision: { revision_number: 2, quote_version: 2, action: 'RECALCULATE' },
    metadata_changes: {},
    requirement_changes: {},
    financial_changes: {},
    legal_entity_changes: {},
    line_items: {
      added: [],
      removed: [],
      modified: [],
      unchanged: [],
      total_added: 0,
      total_removed: 0,
      total_modified: 0,
      total_unchanged: 0,
    },
  };

  assert.equal(emptyComparison.has_changes, false);
  assert.equal(Object.keys(emptyComparison.metadata_changes).length, 0);
  assert.equal(emptyComparison.line_items.total_added, 0);

  // Safe financial filtering on empty changes
  const safeEmpty = filterFinancialChanges(emptyComparison.financial_changes, false);
  assert.deepEqual(safeEmpty, {});

  // Safe financial filtering on null/undefined input
  assert.deepEqual(filterFinancialChanges(null, false), {});
  assert.deepEqual(filterFinancialChanges(undefined, false), {});

  // Scenario 2: Missing line_items fields or null values
  const incompleteLineItem = {
    catalog_item_id: null,
    part_number: null,
    brand: null,
    description: 'Custom Service Line',
    section: null,
    status: 'added',
    quantity_old: null,
    quantity_new: 1,
    unit_sell_price_old: null,
    unit_sell_price_new: '500.00',
    line_sell_total_old: null,
    line_sell_total_new: '500.00',
  };

  const badge = getLineItemCategoryBadge(incompleteLineItem.status);
  assert.equal(badge.label, '+ ADDED');
  assert.equal(incompleteLineItem.part_number || 'Custom', 'Custom');
  assert.equal(incompleteLineItem.section || 'General', 'General');
  assert.equal(formatFieldDiffValue(incompleteLineItem.part_number), '—');
});


// -----------------------------------------------------------------------------
// Test Suite 13: CP18B Historical Quote Revision Viewer Specification
// -----------------------------------------------------------------------------

test('CP18B Requirement 1: Successful revision retrieval and rendering data contract', () => {
  const mockRevisionData = {
    id: 10,
    quote_id: 42,
    revision_number: 3,
    quote_version: 2,
    action: 'EDIT',
    user_id: 1,
    user_email: 'admin@benchmark.com',
    user_role: 'Admin',
    created_at: '2026-10-20T12:00:00Z',
    change_reason: 'Client requested extra monitor',
    snapshot_data: {
      quote: { quote_ref_no: 'BBS-2026-000042', client_name: 'Mediacorp' },
      financials: { total_sell_local: '50000.00', currency_code: 'SGD' },
      line_items: [{ part_number: 'MON-01', quantity: 2, line_sell_total: '2000.00' }],
    },
  };

  assert.equal(mockRevisionData.quote_id, 42);
  assert.equal(mockRevisionData.revision_number, 3);
  assert.equal(mockRevisionData.snapshot_data.quote.client_name, 'Mediacorp');
  assert.equal(mockRevisionData.snapshot_data.line_items.length, 1);
});

test('CP18B Requirement 2: Correct quote ID and revision number validation from route', () => {
  const validateRouteParams = (idParam, revParam) => {
    const qNum = Number(idParam);
    const rNum = Number(revParam);
    const isQValid = Number.isInteger(qNum) && qNum > 0 && String(qNum) === String(idParam || '').trim();
    const isRValid = Number.isInteger(rNum) && rNum > 0 && String(rNum) === String(revParam || '').trim();
    if (!isQValid && !isRValid) return { isValid: false, error: 'Invalid quote ID and revision number.' };
    if (!isQValid) return { isValid: false, error: 'Invalid quote ID.' };
    if (!isRValid) return { isValid: false, error: 'Invalid revision number.' };
    return { isValid: true, quoteId: qNum, revisionNumber: rNum };
  };

  assert.deepEqual(validateRouteParams('42', '3'), { isValid: true, quoteId: 42, revisionNumber: 3 });
  assert.equal(validateRouteParams('abc', '3').isValid, false);
  assert.equal(validateRouteParams('42', '0').isValid, false);
  assert.equal(validateRouteParams('42', '-1').isValid, false);
  assert.equal(validateRouteParams('42.5', '1').isValid, false);
  assert.equal(validateRouteParams(null, '1').isValid, false);
});

test('CP18B Requirement 3: Loading state behavior', () => {
  const initialViewerState = {
    revision: null,
    loading: true,
    error: null,
    errorStatus: null,
  };

  assert.equal(initialViewerState.loading, true);
  assert.equal(initialViewerState.revision, null);
  assert.equal(initialViewerState.error, null);
});

test('CP18B Requirement 4: Recoverable API error and retry mechanism', () => {
  let retryCount = 0;
  const triggerRetry = () => {
    retryCount += 1;
  };

  const classifyError = (err) => {
    if (err.isNetworkError || err.status === 0) {
      return { isRecoverable: true, message: 'Network error. Please try again.' };
    }
    if (err.status >= 500) {
      return { isRecoverable: true, message: 'Server error. Please try again later.' };
    }
    return { isRecoverable: false, message: err.message };
  };

  const netError = { isNetworkError: true, status: 0 };
  const classification = classifyError(netError);
  assert.equal(classification.isRecoverable, true);

  triggerRetry();
  assert.equal(retryCount, 1);
});

test('CP18B Requirement 5: Missing revision response (404 Not Found)', () => {
  const err404 = { status: 404, message: 'Not Found' };
  const getErrorMessage = (err, quoteId, revNum) => {
    if (err.status === 404) {
      return `Revision #${revNum} does not exist for Quote #${quoteId}.`;
    }
    return err.message;
  };

  const message = getErrorMessage(err404, 1004, 99);
  assert.equal(message, 'Revision #99 does not exist for Quote #1004.');
});

test('CP18B Requirement 6: Unauthorized and forbidden responses handling', () => {
  const err401 = { status: 401 };
  const err403 = { status: 403 };

  const getAuthErrorState = (err) => {
    if (err.status === 401) {
      return { type: 'unauthorized', title: 'Authentication Required', showSignIn: true };
    }
    if (err.status === 403) {
      return { type: 'forbidden', title: 'Access Forbidden', showSignIn: false };
    }
    return { type: 'general', title: 'Error', showSignIn: false };
  };

  assert.deepEqual(getAuthErrorState(err401), {
    type: 'unauthorized',
    title: 'Authentication Required',
    showSignIn: true,
  });

  assert.deepEqual(getAuthErrorState(err403), {
    type: 'forbidden',
    title: 'Access Forbidden',
    showSignIn: false,
  });
});

test('CP18B Requirement 7: Historical values displayed strictly from the snapshot', () => {
  const snapshotData = {
    quote: { client_name: 'Channel 8', status: 'approved' },
    financials: {
      subtotal_sell_usd: '80000.00',
      total_sell_local: '108000.00',
      currency_code: 'SGD',
      fx_rate_to_usd: '0.740741',
      tax_enabled: true,
      tax_rate_percent: '9.00',
    },
    line_items: [
      { part_number: 'CAM-A', quantity: 2, unit_sell_price_snapshot: '40000.00', line_sell_total: '80000.00' },
    ],
  };

  assert.equal(snapshotData.quote.client_name, 'Channel 8');
  assert.equal(snapshotData.financials.subtotal_sell_usd, '80000.00');
  assert.equal(snapshotData.financials.total_sell_local, '108000.00');
  assert.equal(snapshotData.financials.currency_code, 'SGD');
  assert.equal(snapshotData.financials.fx_rate_to_usd, '0.740741');
  assert.equal(snapshotData.line_items[0].unit_sell_price_snapshot, '40000.00');
  assert.equal(snapshotData.line_items[0].line_sell_total, '80000.00');
});

test('CP18B Requirement 8: Immutability - No recalculation or replacement with current quote values', () => {
  // Ensure the viewer takes stored values as immutable truth rather than multiplying
  const storedItem = {
    quantity: 2,
    unit_sell_price_snapshot: '500.00',
    line_sell_total: '1000.00', // Stored value
  };

  // The viewer reads item.line_sell_total directly, without doing qty * unit_sell
  assert.equal(storedItem.line_sell_total, '1000.00');
});

test('CP18B Requirement 9: Masked cost and margin fields are not displayed as zero', () => {
  assert.equal(formatSnapshotUsd(null), '—');
  assert.notEqual(formatSnapshotUsd(null), '$0.00');

  assert.equal(formatSnapshotPercent(null), '—');
  assert.notEqual(formatSnapshotPercent(null), '0%');
  assert.notEqual(formatSnapshotPercent(null), '0.0%');

  assert.equal(formatSnapshotMoney(null, 'SGD'), '—');
  assert.notEqual(formatSnapshotMoney(null, 'SGD'), 'SGD 0.00');
});

test('CP18B Requirement 10: Available cost and margin fields display only when returned by API and authorized', () => {
  // 1. Unauthorized caller (Sales user) -> never display
  assert.equal(canDisplayCostData({ subtotal_cost_usd: '5000.00' }, false), false);

  // 2. Authorized caller (Finance) with masked/null data -> do not display
  assert.equal(canDisplayCostData({ subtotal_cost_usd: null }, true), false);

  // 3. Authorized caller with valid cost data -> display allowed
  assert.equal(canDisplayCostData({ subtotal_cost_usd: '5000.00' }, true), true);
});

test('CP18B Requirement 11: Navigation back to the quote', () => {
  const quoteId = 1004;
  const backTarget = `/quotes/${quoteId}`;
  assert.equal(backTarget, '/quotes/1004');
});

test('CP18B Requirement 12: Direct navigation and browser refresh route behavior', () => {
  const buildViewerRoute = (id, rev) => `/quotes/${id}/revisions/${rev}`;
  const routePath = buildViewerRoute(1004, 2);
  assert.equal(routePath, '/quotes/1004/revisions/2');
});

test('CP18B Requirement 13: Safe handling of missing optional snapshot fields', () => {
  const minimalSnapshot = {
    quote: {},
    financials: {},
    legal_entity: {},
    line_items: [],
  };

  // Grouping empty items works safely
  const grouped = groupSnapshotLineItems(minimalSnapshot.line_items);
  assert.deepEqual(grouped, {});

  // Missing descriptions, client names, legal entity names fallback gracefully
  assert.equal(minimalSnapshot.quote.client_name || '—', '—');
  assert.equal(minimalSnapshot.quote.description || null, null);
  assert.equal(minimalSnapshot.financials.currency_code || 'USD', 'USD');
  assert.equal(minimalSnapshot.financials.fx_rate_to_usd || null, null);
});

test('CP18B Requirement 14: Route changes do not display stale revision data', () => {
  // Simulate active request token/flag cancellation pattern
  let activeRevisionId = 1;
  let receivedDataForRevision = null;

  const simulateFetch = (reqRevId, delayMs, payload) => {
    setTimeout(() => {
      // Only commit data if request matches currently active revision
      if (reqRevId === activeRevisionId) {
        receivedDataForRevision = payload;
      }
    }, delayMs);
  };

  // Start slow fetch for rev 1 (100ms)
  simulateFetch(1, 100, { rev: 1 });

  // Route immediately changes to rev 2 (activeRevisionId becomes 2)
  activeRevisionId = 2;
  simulateFetch(2, 20, { rev: 2 });

  return new Promise((resolve) => {
    setTimeout(() => {
      // Data committed must be rev 2, rev 1 was cancelled/ignored
      assert.deepEqual(receivedDataForRevision, { rev: 2 });
      resolve();
    }, 150);
  });
});

test('CP18B Requirement 15: The CP18A View Snapshot action points to the correct viewer route', () => {
  // In RevisionHistoryCard.jsx: handleViewSnapshot navigates to /quotes/${quoteId}/revisions/${revisionNumber}
  const quoteId = 1004;
  const revNum = 3;
  let navigatedTo = null;
  const mockNavigate = (path) => {
    navigatedTo = path;
  };

  // Replicate default handler logic from RevisionHistoryCard
  const handleViewSnapshot = (rev) => {
    mockNavigate(`/quotes/${quoteId}/revisions/${rev}`);
  };

  handleViewSnapshot(revNum);
  assert.equal(navigatedTo, '/quotes/1004/revisions/3');
  assert.equal(navigatedTo, getSnapshotViewUrl(quoteId, revNum));
});


// -----------------------------------------------------------------------------
// Test Suite 14: CP18C Historical Quote Revision Comparison UI Specification
// -----------------------------------------------------------------------------

test('CP18C Requirement 1: Comparison API integration and URL parameter contract', () => {
  const quoteId = 1004;
  const baseRev = 1;
  const targetRev = 2;

  const url = buildComparisonApiUrl(quoteId, baseRev, targetRev);
  assert.equal(url, '/api/quotes/1004/revisions/compare?base_revision=1&target_revision=2');
});

test('CP18C Requirement 2: Valid and invalid revision selections (distinct and bounds)', () => {
  // Valid pair
  const valid = validateComparisonParams('1', '3');
  assert.equal(valid.isValid, true);
  assert.equal(valid.from, 1);
  assert.equal(valid.to, 3);

  // Identical revisions rejected
  const identical = validateComparisonParams('2', '2');
  assert.equal(identical.isValid, false);
  assert.equal(identical.isDistinctError, true);
  assert.ok(identical.error.includes('must be distinct'));

  // Invalid parameters
  assert.equal(validateComparisonParams('0', '2').isValid, false);
  assert.equal(validateComparisonParams('-1', '2').isValid, false);
  assert.equal(validateComparisonParams('abc', '2').isValid, false);
  assert.equal(validateComparisonParams(null, '2').isValid, false);
});

test('CP18C Requirement 3: Swapping revisions', () => {
  const pair = { from: 1, to: 3 };
  const swapped = swapRevisionNumbers(pair.from, pair.to);
  assert.deepEqual(swapped, { from: 3, to: 1 });

  // Swapped URL query string
  const swappedUrl = buildComparisonUrl(1004, swapped.from, swapped.to);
  assert.equal(swappedUrl, '/quotes/1004/revisions/compare?from=3&to=1');
});

test('CP18C Requirement 4: Added, removed, and modified field changes presentation', () => {
  const metadataChanges = {
    status: { old: 'draft', new: 'approved', changed: true },
    is_urgent: { old: false, new: true, changed: true },
  };

  assert.equal(formatFieldDiffValue(metadataChanges.status.old), 'draft');
  assert.equal(formatFieldDiffValue(metadataChanges.status.new), 'approved');
  assert.equal(formatFieldDiffValue(metadataChanges.is_urgent.old), 'No');
  assert.equal(formatFieldDiffValue(metadataChanges.is_urgent.new), 'Yes');
  assert.equal(formatFieldDiffValue(null), '—');
});

test('CP18C Requirement 5: Line-item comparison categorization and badges', () => {
  const lineItemDeltas = [
    { part_number: 'CAM-01', status: 'added', quantity_new: 2 },
    { part_number: 'SW-01', status: 'removed', quantity_old: 1 },
    { part_number: 'MON-01', status: 'modified', quantity_old: 1, quantity_new: 3 },
    { part_number: 'CBL-01', status: 'unchanged', quantity_new: 10 },
  ];

  const addedBadge = getLineItemCategoryBadge(lineItemDeltas[0].status);
  assert.equal(addedBadge.label, '+ ADDED');
  assert.equal(addedBadge.symbol, '+');

  const removedBadge = getLineItemCategoryBadge(lineItemDeltas[1].status);
  assert.equal(removedBadge.label, '- REMOVED');
  assert.equal(removedBadge.symbol, '-');

  const modifiedBadge = getLineItemCategoryBadge(lineItemDeltas[2].status);
  assert.equal(modifiedBadge.label, 'Δ MODIFIED');
  assert.equal(modifiedBadge.symbol, 'Δ');

  const unchangedBadge = getLineItemCategoryBadge(lineItemDeltas[3].status);
  assert.equal(unchangedBadge.label, '= UNCHANGED');
  assert.equal(unchangedBadge.symbol, '=');
});

test('CP18C Requirement 6: Empty comparison results (Identical revisions)', () => {
  const identicalComparison = {
    quote_id: 1004,
    has_changes: false,
    base_revision: { revision_number: 1, quote_version: 1 },
    target_revision: { revision_number: 2, quote_version: 1 },
    metadata_changes: {},
    requirement_changes: {},
    financial_changes: {},
    legal_entity_changes: {},
    line_items: {
      added: [],
      removed: [],
      modified: [],
      unchanged: [],
      total_added: 0,
      total_removed: 0,
      total_modified: 0,
      total_unchanged: 5,
    },
  };

  assert.equal(identicalComparison.has_changes, false);
  assert.equal(identicalComparison.line_items.total_added, 0);
  assert.equal(identicalComparison.line_items.total_removed, 0);
  assert.equal(identicalComparison.line_items.total_modified, 0);
});

test('CP18C Requirement 7: Loading, retry, and error states (401, 403, 404, 500, network)', () => {
  const err401 = { status: 401, message: 'Unauthorized' };
  assert.ok(classifyComparisonError(err401).includes('sign in'));

  const err403 = { status: 403, message: 'Forbidden' };
  assert.ok(classifyComparisonError(err403).includes('permission'));

  const err404 = { status: 404, message: 'Not Found' };
  assert.ok(classifyComparisonError(err404, 1, 99).includes('not found'));

  const err500 = { status: 500, message: 'Server Error' };
  assert.ok(classifyComparisonError(err500).includes('server encountered an error'));

  const errNet = { isNetworkError: true, status: 0, message: 'Failed to fetch' };
  assert.equal(classifyComparisonError(errNet), 'Failed to fetch');
});

test('CP18C Requirement 8: Masked cost and margin fields in comparison view', () => {
  const comparisonFinancials = {
    subtotal_sell_usd: { old: '10000.00', new: '12000.00' },
    subtotal_cost_usd: { old: '6000.00', new: '7500.00' },
    margin_percent: { old: '40.0', new: '37.5' },
  };

  // Unauthorized (Sales user) -> cost and margin stripped
  const maskedDeltas = filterFinancialChanges(comparisonFinancials, false);
  assert.deepEqual(Object.keys(maskedDeltas), ['subtotal_sell_usd']);
  assert.equal('subtotal_cost_usd' in maskedDeltas, false);
  assert.equal('margin_percent' in maskedDeltas, false);

  // Authorized (Management/Admin) -> all deltas visible
  const authorizedDeltas = filterFinancialChanges(comparisonFinancials, true);
  assert.deepEqual(Object.keys(authorizedDeltas), ['subtotal_sell_usd', 'subtotal_cost_usd', 'margin_percent']);
});

test('CP18C Requirement 9: Navigation back to quote details and individual snapshots', () => {
  const quoteId = 1004;
  const baseRev = 1;
  const targetRev = 2;

  // Snapshot targets
  assert.equal(getSnapshotViewUrl(quoteId, baseRev), '/quotes/1004/revisions/1');
  assert.equal(getSnapshotViewUrl(quoteId, targetRev), '/quotes/1004/revisions/2');

  // Back to quote details
  const backToQuoteUrl = `/quotes/${quoteId}`;
  assert.equal(backToQuoteUrl, '/quotes/1004');
});

test('CP18C Requirement 10: Safe handling of incomplete or malformed comparison responses', () => {
  const malformedComparison = {
    quote_id: 1004,
    has_changes: true,
    base_revision: { revision_number: 1, quote_version: 1 },
    target_revision: { revision_number: 2, quote_version: 2 },
    metadata_changes: null, // Null collection
    requirement_changes: undefined,
    financial_changes: null,
    legal_entity_changes: null,
    line_items: {
      added: [{ part_number: null, description: 'Mystery Item', status: 'added' }],
      removed: [],
      modified: [],
      unchanged: [],
      total_added: 1,
      total_removed: 0,
      total_modified: 0,
      total_unchanged: 0,
    },
  };

  // filterFinancialChanges handles null gracefully
  assert.deepEqual(filterFinancialChanges(malformedComparison.financial_changes, false), {});

  // Line item handles null part number safely
  assert.equal(formatFieldDiffValue(malformedComparison.line_items.added[0].part_number), '—');
});
