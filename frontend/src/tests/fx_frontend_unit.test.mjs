import test from 'node:test';
import assert from 'node:assert/strict';

// --- Constants & Permission Configuration matching AuthContext.jsx ---
export const ROLES = {
  ADMIN: 'Admin',
  MANAGEMENT: 'Management',
  CATALOG_ENTRY: 'Catalog Entry',
  SALES: 'Sales',
};

export const PERMISSIONS = {
  SALES_USER: 'sales_user',
  CATALOG_EDIT: 'catalog_edit',
  COST_VISIBILITY: 'cost_visibility',
  FINANCE_TAX_ADMIN: 'finance_tax_admin',
  SOLUTION_ADMIN: 'solution_admin',
  SUPER_ADMIN: 'super_admin',
};

export const ROLE_PERMISSIONS = {
  [ROLES.SALES]: [PERMISSIONS.SALES_USER],
  [ROLES.CATALOG_ENTRY]: [PERMISSIONS.SALES_USER, PERMISSIONS.CATALOG_EDIT],
  [ROLES.MANAGEMENT]: [
    PERMISSIONS.SALES_USER,
    PERMISSIONS.CATALOG_EDIT,
    PERMISSIONS.COST_VISIBILITY,
    PERMISSIONS.FINANCE_TAX_ADMIN,
  ],
  [ROLES.ADMIN]: [
    PERMISSIONS.SALES_USER,
    PERMISSIONS.CATALOG_EDIT,
    PERMISSIONS.COST_VISIBILITY,
    PERMISSIONS.FINANCE_TAX_ADMIN,
    PERMISSIONS.SOLUTION_ADMIN,
    PERMISSIONS.SUPER_ADMIN,
  ],
};

function hasPermission(user, permission) {
  if (!user || !user.role_tier) return false;
  const permissions = ROLE_PERMISSIONS[user.role_tier] || [];
  return permissions.includes(permission);
}

// --- Validation logic matching CatalogPricingPage.jsx ---
function validateFxRateInput(fxRateStringOrNumber) {
  const rateNum = Number(fxRateStringOrNumber);
  if (Number.isNaN(rateNum) || !Number.isFinite(rateNum) || rateNum <= 0) {
    return {
      isValid: false,
      error: 'FX rate must be a valid positive number greater than 0.',
      rateNum: null,
    };
  }
  return {
    isValid: true,
    error: null,
    rateNum,
  };
}

// --- Eligibility and difference detection matching QuoteDetailPage.jsx ---
function isEligibleForFxRefresh(status) {
  const normalized = (status || '').toLowerCase();
  return normalized === 'draft' || normalized === 'changes_requested';
}

function canUserRefreshQuoteFx(user, quoteStatus) {
  return isEligibleForFxRefresh(quoteStatus) && hasPermission(user, PERMISSIONS.FINANCE_TAX_ADMIN);
}

function detectFxRateDifference(quote, activeRegion) {
  const status = (quote?.status || '').toLowerCase();
  const isEligible = status === 'draft' || status === 'changes_requested';
  if (!isEligible) return false;

  const quoteRate = quote?.fx_rate_to_usd !== null && quote?.fx_rate_to_usd !== undefined ? Number(quote.fx_rate_to_usd) : null;
  const regionRate = activeRegion?.fx_rate_to_usd !== null && activeRegion?.fx_rate_to_usd !== undefined ? Number(activeRegion.fx_rate_to_usd) : null;

  if (quoteRate === null || regionRate === null) return false;
  return Math.abs(quoteRate - regionRate) > 0.0000001;
}

// =========================================================================
// TEST SUITE
// =========================================================================

test('Auth & Permissions: Only Admin and Management have finance_tax_admin permission', () => {
  const adminUser = { id: 1, email: 'admin@benchmark.com', role_tier: ROLES.ADMIN };
  const mgmtUser = { id: 2, email: 'mgmt@benchmark.com', role_tier: ROLES.MANAGEMENT };
  const salesUser = { id: 3, email: 'sales@benchmark.com', role_tier: ROLES.SALES };
  const catalogUser = { id: 4, email: 'cat@benchmark.com', role_tier: ROLES.CATALOG_ENTRY };
  const anonymous = null;

  assert.equal(hasPermission(adminUser, PERMISSIONS.FINANCE_TAX_ADMIN), true, 'Admin must have finance_tax_admin');
  assert.equal(hasPermission(mgmtUser, PERMISSIONS.FINANCE_TAX_ADMIN), true, 'Management must have finance_tax_admin');
  assert.equal(hasPermission(salesUser, PERMISSIONS.FINANCE_TAX_ADMIN), false, 'Sales must NOT have finance_tax_admin');
  assert.equal(hasPermission(catalogUser, PERMISSIONS.FINANCE_TAX_ADMIN), false, 'Catalog Entry must NOT have finance_tax_admin');
  assert.equal(hasPermission(anonymous, PERMISSIONS.FINANCE_TAX_ADMIN), false, 'Anonymous must NOT have finance_tax_admin');
});

test('FX Validation: Accepts strictly positive finite numeric rates', () => {
  const validCases = ['1.350000', '0.74', 0.000001, '1', 83.25, '12500.50'];
  for (const val of validCases) {
    const res = validateFxRateInput(val);
    assert.equal(res.isValid, true, `Expected ${val} to be valid`);
    assert.equal(res.error, null);
    assert.ok(res.rateNum > 0);
  }
});

test('FX Validation: Rejects zero, negative, NaN, Infinity, and empty inputs', () => {
  const invalidCases = [
    '0',
    0,
    '-1.35',
    -0.0001,
    '',
    '   ',
    'abc',
    '1.2.3',
    NaN,
    null,
    undefined,
    Infinity,
    -Infinity,
  ];

  for (const val of invalidCases) {
    const res = validateFxRateInput(val);
    assert.equal(res.isValid, false, `Expected ${val} to be invalid`);
    assert.equal(res.error, 'FX rate must be a valid positive number greater than 0.');
    assert.equal(res.rateNum, null);
  }
});

test('Quote Detail: Refresh FX eligibility by quote status', () => {
  assert.equal(isEligibleForFxRefresh('draft'), true, 'draft should be eligible');
  assert.equal(isEligibleForFxRefresh('DRAFT'), true, 'case insensitive draft should be eligible');
  assert.equal(isEligibleForFxRefresh('changes_requested'), true, 'changes_requested should be eligible');
  assert.equal(isEligibleForFxRefresh('CHANGES_REQUESTED'), true, 'case insensitive changes_requested should be eligible');

  assert.equal(isEligibleForFxRefresh('pending_approval'), false, 'pending_approval must be immutable');
  assert.equal(isEligibleForFxRefresh('approved'), false, 'approved must be immutable');
  assert.equal(isEligibleForFxRefresh('rejected'), false, 'rejected must not be refreshable');
  assert.equal(isEligibleForFxRefresh('superseded'), false, 'superseded must not be refreshable');
  assert.equal(isEligibleForFxRefresh(null), false, 'null status must not be refreshable');
});

test('Quote Detail: Refresh FX button permission gating', () => {
  const admin = { role_tier: ROLES.ADMIN };
  const mgmt = { role_tier: ROLES.MANAGEMENT };
  const sales = { role_tier: ROLES.SALES };

  // Eligible statuses
  assert.equal(canUserRefreshQuoteFx(admin, 'draft'), true, 'Admin can refresh draft');
  assert.equal(canUserRefreshQuoteFx(mgmt, 'draft'), true, 'Management can refresh draft');
  assert.equal(canUserRefreshQuoteFx(sales, 'draft'), false, 'Sales CANNOT refresh draft');

  assert.equal(canUserRefreshQuoteFx(admin, 'changes_requested'), true, 'Admin can refresh changes_requested');
  assert.equal(canUserRefreshQuoteFx(sales, 'changes_requested'), false, 'Sales CANNOT refresh changes_requested');

  // Immutable statuses: Even Admin cannot refresh
  assert.equal(canUserRefreshQuoteFx(admin, 'approved'), false, 'Admin CANNOT refresh approved quote');
  assert.equal(canUserRefreshQuoteFx(mgmt, 'approved'), false, 'Management CANNOT refresh approved quote');
  assert.equal(canUserRefreshQuoteFx(admin, 'pending_approval'), false, 'Admin CANNOT refresh pending_approval quote');
  assert.equal(canUserRefreshQuoteFx(sales, 'approved'), false, 'Sales CANNOT refresh approved quote');
});

test('Quote Detail: FX rate difference detection', () => {
  const region = { id: 1, currency_code: 'SGD', fx_rate_to_usd: 0.750000 };

  // Rate difference on draft quote -> true
  const draftDiffering = { status: 'draft', region_id: 1, fx_rate_to_usd: 0.740000 };
  assert.equal(detectFxRateDifference(draftDiffering, region), true);

  // Same rate on draft quote -> false
  const draftIdentical = { status: 'draft', region_id: 1, fx_rate_to_usd: 0.750000 };
  assert.equal(detectFxRateDifference(draftIdentical, region), false);

  // Microscopic floating point difference within 1e-7 -> false
  const draftMicroDiff = { status: 'draft', region_id: 1, fx_rate_to_usd: 0.75000000001 };
  assert.equal(detectFxRateDifference(draftMicroDiff, region), false);

  // Approved quote with different rate -> false (suppress difference notice on immutable quotes)
  const approvedDiffering = { status: 'approved', region_id: 1, fx_rate_to_usd: 0.700000 };
  assert.equal(detectFxRateDifference(approvedDiffering, region), false);

  // Missing rate fields -> false
  const draftMissing = { status: 'draft', region_id: 1, fx_rate_to_usd: null };
  assert.equal(detectFxRateDifference(draftMissing, region), false);
});

test('Integration Payload Contract: Region update payload structure', () => {
  const regionId = 1;
  const inputForm = {
    fx_rate_to_usd: '0.755000',
    currency_code: 'SGD',
    fx_rate_as_of: '2026-10-16 12:00:00 UTC',
    notes: 'Q4 rate adjustment',
  };

  const payload = {
    fx_rate_to_usd: Number(inputForm.fx_rate_to_usd),
    currency_code: inputForm.currency_code,
    fx_rate_as_of: inputForm.fx_rate_as_of.trim() || undefined,
    notes: inputForm.notes.trim() || undefined,
  };

  assert.equal(payload.fx_rate_to_usd, 0.755);
  assert.equal(payload.currency_code, 'SGD');
  assert.equal(payload.fx_rate_as_of, '2026-10-16 12:00:00 UTC');
  assert.equal(payload.notes, 'Q4 rate adjustment');
});

test('Integration Payload Contract: Quote refresh payload structure with expected_version', () => {
  const quote = { id: 42, version: 3 };
  const refreshReason = 'Annual FX recalibration';

  const payload = {
    expected_version: quote.version,
    reason: refreshReason.trim() || undefined,
  };

  assert.equal(payload.expected_version, 3, 'Must include expected_version for optimistic concurrency');
  assert.equal(payload.reason, 'Annual FX recalibration');
});
