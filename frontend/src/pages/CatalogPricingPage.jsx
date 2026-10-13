import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import PageHeader from '../components/common/PageHeader';
import { catalogApi } from '../api/catalogApi';
import { solutionApi } from '../api/solutionApi';
import { useAuth, PERMISSIONS, ROLES } from '../auth/AuthContext';

function formatCurrencyCell(value) {
  if (value === null || value === undefined || value === '') {
    return (
      <span className="badge badge-warning" title="Database value is NULL (unpriced)">
        Unpriced (NULL)
      </span>
    );
  }
  const num = Number(value);
  if (Number.isNaN(num)) {
    return String(value);
  }
  return `$${num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function CatalogPricingPage() {
  const { hasPermission, isRole } = useAuth();
  const isAdmin = hasPermission(PERMISSIONS.SUPER_ADMIN);
  const canManageSolutions = hasPermission(PERMISSIONS.SOLUTION_ADMIN);
  const canEditMargin = hasPermission(PERMISSIONS.FINANCE_TAX_ADMIN);
  const hasFullCostVisibility = hasPermission(PERMISSIONS.COST_VISIBILITY);

  const [solutions, setSolutions] = useState([]);
  const [selectedSolutionId, setSelectedSolutionId] = useState('');
  const [catalogSettings, setCatalogSettings] = useState({
    catalog_entry_cost_visibility: true,
  });

  const [items, setItems] = useState([]);
  const [isLoadingSolutions, setIsLoadingSolutions] = useState(true);
  const [isLoadingItems, setIsLoadingItems] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Filters
  const [searchQ, setSearchQ] = useState('');
  const [partFilter, setPartFilter] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [kindFilter, setKindFilter] = useState('');
  const [priceStatusFilter, setPriceStatusFilter] = useState('ALL');

  // Margin form state
  const [marginInput, setMarginInput] = useState('');
  const [isSavingMargin, setIsSavingMargin] = useState(false);

  // Settings toggle state
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // Product modal state (Add / Edit)
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [productForm, setProductForm] = useState({
    part_number: '',
    description: '',
    brand: '',
    sell_price: '',
    cost_price: '',
  });
  const [productModalError, setProductModalError] = useState('');
  const [isSavingProduct, setIsSavingProduct] = useState(false);

  // Solution modal state (Create / Edit)
  const [solutionModalOpen, setSolutionModalOpen] = useState(false);
  const [solutionModalMode, setSolutionModalMode] = useState('create');
  const [solutionForm, setSolutionForm] = useState({
    name: '',
    code: '',
    default_margin_percent: '15.00',
  });
  const [solutionModalError, setSolutionModalError] = useState('');
  const [isSavingSolution, setIsSavingSolution] = useState(false);

  // Import state
  const fileInputRef = useRef(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importRowErrors, setImportRowErrors] = useState([]);

  const canViewCatalogCost =
    hasFullCostVisibility ||
    (isRole(ROLES.CATALOG_ENTRY) && catalogSettings.catalog_entry_cost_visibility);

  const selectedSolution = useMemo(
    () =>
      solutions.find((s) => String(s.id) === String(selectedSolutionId)) || null,
    [solutions, selectedSolutionId]
  );

  const loadInitialData = useCallback(async () => {
    setIsLoadingSolutions(true);
    setError('');
    try {
      const [solsData, settingsData] = await Promise.all([
        solutionApi.getSolutions(),
        catalogApi.getCatalogSettings(),
      ]);
      setSolutions(solsData);
      setCatalogSettings(settingsData);
      if (solsData.length > 0) {
        const defaultSol =
          solsData.find((s) => s.name === 'WTVision Graphics') || solsData[0];
        setSelectedSolutionId(defaultSol.id);
        setMarginInput(
          defaultSol.default_margin_percent !== null &&
            defaultSol.default_margin_percent !== undefined
            ? String(defaultSol.default_margin_percent)
            : ''
        );
      }
    } catch (err) {
      setError(err.message || 'Failed to load catalog configuration.');
    } finally {
      setIsLoadingSolutions(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const loadCatalogItems = useCallback(async () => {
    if (!selectedSolutionId) return;
    setIsLoadingItems(true);
    setError('');
    try {
      const data = await catalogApi.getCatalogItems({
        solutionId: selectedSolutionId,
        q: searchQ.trim(),
        partNumber: partFilter.trim(),
        brand: brandFilter.trim(),
        kind: kindFilter,
      });
      setItems(data);
    } catch (err) {
      setError(err.message || 'Failed to load catalog items.');
    } finally {
      setIsLoadingItems(false);
    }
  }, [selectedSolutionId, searchQ, partFilter, brandFilter, kindFilter]);

  useEffect(() => {
    loadCatalogItems();
  }, [loadCatalogItems]);

  const handleSolutionChange = (e) => {
    const newId = e.target.value;
    setSelectedSolutionId(newId);
    setImportRowErrors([]);
    setSuccessMessage('');
    const sol = solutions.find((s) => String(s.id) === String(newId));
    if (sol) {
      setMarginInput(
        sol.default_margin_percent !== null &&
          sol.default_margin_percent !== undefined
          ? String(sol.default_margin_percent)
          : ''
      );
    }
  };

  // Detect duplicate part numbers within the loaded catalog list
  const duplicatePartNumbers = useMemo(() => {
    const counts = {};
    items.forEach((item) => {
      if (item.part_number) {
        counts[item.part_number] = (counts[item.part_number] || 0) + 1;
      }
    });
    return new Set(
      Object.keys(counts).filter((pn) => counts[pn] > 1)
    );
  }, [items]);

  const filteredItems = useMemo(() => {
    if (priceStatusFilter === 'ALL') return items;
    if (priceStatusFilter === 'UNPRICED') {
      return items.filter(
        (item) =>
          item.sell_price === null ||
          item.sell_price === undefined ||
          (canViewCatalogCost &&
            (item.cost_price === null || item.cost_price === undefined))
      );
    }
    if (priceStatusFilter === 'PRICED') {
      return items.filter(
        (item) => item.sell_price !== null && item.sell_price !== undefined
      );
    }
    return items;
  }, [items, priceStatusFilter, canViewCatalogCost]);

  const handleToggleCostVisibility = async (e) => {
    const nextValue = e.target.checked;
    setIsSavingSettings(true);
    setError('');
    setSuccessMessage('');
    try {
      const updated = await catalogApi.updateCatalogSettings(nextValue);
      setCatalogSettings(updated);
      setSuccessMessage(
        `Catalog Entry cost visibility is now ${
          updated.catalog_entry_cost_visibility ? 'enabled' : 'disabled'
        }.`
      );
      await loadCatalogItems();
    } catch (err) {
      setError(err.message || 'Failed to update cost visibility setting.');
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleSaveMargin = async (e) => {
    e.preventDefault();
    if (!selectedSolution) return;
    const parsed = Number(marginInput);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 100) {
      setError('Default margin must be a number between 0 and 100.');
      return;
    }
    setIsSavingMargin(true);
    setError('');
    setSuccessMessage('');
    try {
      const updated = await solutionApi.updateSolutionMargin(
        selectedSolution.id,
        parsed
      );
      setSolutions((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s))
      );
      setMarginInput(String(updated.default_margin_percent));
      setSuccessMessage(
        `Updated default margin for "${updated.name}" to ${updated.default_margin_percent}%.`
      );
    } catch (err) {
      setError(err.message || 'Failed to update solution margin.');
    } finally {
      setIsSavingMargin(false);
    }
  };

  const openAddProductModal = () => {
    setEditingItem(null);
    setProductForm({
      part_number: '',
      description: '',
      brand: '',
      sell_price: '',
      cost_price: '',
    });
    setProductModalError('');
    setProductModalOpen(true);
  };

  const openEditProductModal = (item) => {
    setEditingItem(item);
    setProductForm({
      part_number: item.part_number || '',
      description: item.description || '',
      brand: item.brand || '',
      sell_price:
        item.sell_price !== null && item.sell_price !== undefined
          ? String(item.sell_price)
          : '',
      cost_price:
        item.cost_price !== null && item.cost_price !== undefined
          ? String(item.cost_price)
          : '',
    });
    setProductModalError('');
    setProductModalOpen(true);
  };

  const handleSaveProduct = async (e) => {
    e.preventDefault();
    setProductModalError('');
    const cleanDesc = productForm.description.trim();
    if (!cleanDesc) {
      setProductModalError('Description is required.');
      return;
    }

    const parsePriceField = (raw, label) => {
      const trimmed = String(raw).trim();
      if (trimmed === '') return null;
      const num = Number(trimmed);
      if (Number.isNaN(num) || num < 0) {
        throw new Error(`${label} must be a non-negative number or left blank for NULL.`);
      }
      return num;
    };

    let sellPriceVal;
    let costPriceVal;
    try {
      sellPriceVal = parsePriceField(productForm.sell_price, 'Sell Price');
      if (canViewCatalogCost) {
        costPriceVal = parsePriceField(productForm.cost_price, 'Cost Price');
      }
    } catch (validationErr) {
      setProductModalError(validationErr.message);
      return;
    }

    setIsSavingProduct(true);
    try {
      if (editingItem) {
        const updatePayload = {
          description: cleanDesc,
          brand: productForm.brand.trim() || null,
          sell_price: sellPriceVal,
        };
        if (editingItem.kind !== 'rule_driven') {
          updatePayload.part_number = productForm.part_number.trim() || null;
        }
        if (canViewCatalogCost) {
          updatePayload.cost_price = costPriceVal;
        }
        await catalogApi.updateCatalogItem(editingItem.id, updatePayload);
        setSuccessMessage(`Updated catalog item "${cleanDesc}".`);
      } else {
        const createPayload = {
          solution_id: Number(selectedSolutionId),
          kind: 'reference',
          part_number: productForm.part_number.trim() || null,
          description: cleanDesc,
          brand: productForm.brand.trim() || null,
          sell_price: sellPriceVal,
        };
        if (canViewCatalogCost && costPriceVal !== null) {
          createPayload.cost_price = costPriceVal;
        }
        await catalogApi.createCatalogItem(createPayload);
        setSuccessMessage(`Created new Reference product "${cleanDesc}".`);
      }
      setProductModalOpen(false);
      await loadCatalogItems();
    } catch (err) {
      setProductModalError(err.message || 'Failed to save catalog item.');
    } finally {
      setIsSavingProduct(false);
    }
  };

  const handleDeleteProduct = async (item) => {
    if (item.kind === 'rule_driven') return;
    if (
      !window.confirm(
        `Are you sure you want to delete Reference product "${item.description}" (ID: ${item.id})?`
      )
    ) {
      return;
    }
    setError('');
    setSuccessMessage('');
    try {
      await catalogApi.deleteCatalogItem(item.id);
      setSuccessMessage(`Deleted product "${item.description}" (ID: ${item.id}).`);
      await loadCatalogItems();
    } catch (err) {
      setError(err.message || 'Failed to delete product.');
    }
  };

  const handleExportExcel = async () => {
    if (!selectedSolution) return;
    setError('');
    try {
      await catalogApi.downloadCatalogExport(
        selectedSolution.id,
        selectedSolution.code || selectedSolution.name
      );
    } catch (err) {
      setError(err.message || 'Failed to export catalog.');
    }
  };

  const handleDownloadTemplate = async () => {
    setError('');
    try {
      await catalogApi.downloadCatalogTemplate();
    } catch (err) {
      setError(err.message || 'Failed to download template.');
    }
  };

  const handleImportFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !selectedSolution) return;
    e.target.value = '';

    setIsImporting(true);
    setError('');
    setSuccessMessage('');
    setImportRowErrors([]);
    try {
      const result = await catalogApi.importCatalogExcel(
        selectedSolution.id,
        file
      );
      setSuccessMessage(
        `${result.message}: ${result.created_count ?? 0} created, ${
          result.updated_count ?? 0
        } updated.`
      );
      await loadCatalogItems();
    } catch (err) {
      setError(err.message || 'Excel import failed.');
      if (err.rowErrors) {
        setImportRowErrors(err.rowErrors);
      }
    } finally {
      setIsImporting(false);
    }
  };

  const handleResetCatalog = async () => {
    if (!selectedSolution || selectedSolution.name !== 'WTVision Graphics') {
      return;
    }
    if (
      !window.confirm(
        'Reset shipped WTVision Graphics catalog items back to their default baseline prices and descriptions? User-added Reference items will be preserved.'
      )
    ) {
      return;
    }
    setError('');
    setSuccessMessage('');
    try {
      const res = await solutionApi.resetCatalogToDefaults(selectedSolution.id);
      setSuccessMessage(res.message || 'Catalog reset to defaults.');
      await loadCatalogItems();
    } catch (err) {
      setError(err.message || 'Failed to reset catalog.');
    }
  };

  const openCreateSolutionModal = () => {
    setSolutionModalMode('create');
    setSolutionForm({
      name: '',
      code: '',
      default_margin_percent: '15.00',
    });
    setSolutionModalError('');
    setSolutionModalOpen(true);
  };

  const openEditSolutionModal = () => {
    if (!selectedSolution) return;
    setSolutionModalMode('edit');
    setSolutionForm({
      name: selectedSolution.name || '',
      code: selectedSolution.code || '',
      default_margin_percent:
        selectedSolution.default_margin_percent !== null &&
        selectedSolution.default_margin_percent !== undefined
          ? String(selectedSolution.default_margin_percent)
          : '15.00',
    });
    setSolutionModalError('');
    setSolutionModalOpen(true);
  };

  const handleSaveSolution = async (e) => {
    e.preventDefault();
    setSolutionModalError('');
    const cleanName = solutionForm.name.trim();
    if (!cleanName) {
      setSolutionModalError('Solution name is required.');
      return;
    }
    const marginVal = Number(solutionForm.default_margin_percent);
    if (Number.isNaN(marginVal) || marginVal < 0 || marginVal > 100) {
      setSolutionModalError('Default margin must be between 0 and 100.');
      return;
    }

    setIsSavingSolution(true);
    try {
      const payload = {
        name: cleanName,
        code: solutionForm.code.trim() || null,
        default_margin_percent: marginVal,
        requirement_schema:
          solutionModalMode === 'edit' && selectedSolution
            ? selectedSolution.requirement_schema || {}
            : {},
        business_rules:
          solutionModalMode === 'edit' && selectedSolution
            ? selectedSolution.business_rules || {}
            : {},
      };
      if (solutionModalMode === 'create') {
        const created = await solutionApi.createSolution(payload);
        const updatedSols = await solutionApi.getSolutions();
        setSolutions(updatedSols);
        setSelectedSolutionId(created.id);
        setMarginInput(String(created.default_margin_percent ?? marginVal));
        setSuccessMessage(
          `Created solution "${created.name}" (${
            created.engine_status === 'active'
              ? 'Engine Active'
              : 'Engine Pending'
          }).`
        );
      } else if (selectedSolution) {
        const updated = await solutionApi.updateSolution(
          selectedSolution.id,
          payload
        );
        setSolutions((prev) =>
          prev.map((s) => (s.id === updated.id ? updated : s))
        );
        setMarginInput(String(updated.default_margin_percent ?? marginVal));
        setSuccessMessage(`Updated solution "${updated.name}".`);
      }
      setSolutionModalOpen(false);
    } catch (err) {
      setSolutionModalError(err.message || 'Failed to save solution.');
    } finally {
      setIsSavingSolution(false);
    }
  };

  if (isLoadingSolutions) {
    return (
      <div className="page-container">
        <div className="loading-container">Loading catalog configuration...</div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Catalog & Pricing"
        subtitle="Manage solution catalogs, reference products, pricing, and safe Excel imports/exports"
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {canManageSolutions && (
              <>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={openEditSolutionModal}
                  disabled={!selectedSolution}
                >
                  Edit Solution
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={openCreateSolutionModal}
                >
                  + New Solution
                </button>
              </>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={openAddProductModal}
              disabled={!selectedSolution}
            >
              + Add Product
            </button>
          </div>
        }
      />

      {error && (
        <div
          className="alert alert-danger"
          style={{
            marginBottom: '1rem',
            padding: '0.875rem 1rem',
            backgroundColor: '#fef2f2',
            color: '#991b1b',
            border: '1px solid #fecaca',
            borderRadius: '0.375rem',
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {successMessage && (
        <div
          className="alert alert-success"
          style={{
            marginBottom: '1rem',
            padding: '0.875rem 1rem',
            backgroundColor: '#dcfce3',
            color: '#166534',
            border: '1px solid #bbf7d0',
            borderRadius: '0.375rem',
          }}
        >
          {successMessage}
        </div>
      )}

      {importRowErrors.length > 0 && (
        <div
          style={{
            marginBottom: '1.5rem',
            padding: '1rem',
            backgroundColor: '#fff1f2',
            border: '1px solid #fecdd3',
            borderRadius: '0.5rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.75rem',
            }}
          >
            <h4 style={{ margin: 0, color: '#9f1239' }}>
              Excel Import Row Validation Errors (Entire Import Rolled Back)
            </h4>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setImportRowErrors([])}
              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
            >
              Dismiss
            </button>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Excel Row</th>
                  <th>Validation Errors</th>
                </tr>
              </thead>
              <tbody>
                {importRowErrors.map((errObj, idx) => (
                  <tr key={idx}>
                    <td>
                      <strong>Row {errObj.row}</strong>
                    </td>
                    <td style={{ color: '#9f1239' }}>
                      {(errObj.errors || []).join('; ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Solution Context & Governance Panel */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div
          style={{
            padding: '1.25rem',
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '0.5rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.5rem',
            }}
          >
            <label
              htmlFor="catalog-solution-select"
              style={{ fontWeight: 600, fontSize: '0.875rem', color: '#334155' }}
            >
              Active Solution Catalog
            </label>
            {selectedSolution && (
              <span
                className={`badge ${
                  selectedSolution.engine_status === 'active'
                    ? 'badge-success'
                    : 'badge-warning'
                }`}
              >
                {selectedSolution.engine_status === 'active'
                  ? 'Engine Active'
                  : 'Engine Pending'}
              </span>
            )}
          </div>
          <select
            id="catalog-solution-select"
            className="form-select"
            value={selectedSolutionId}
            onChange={handleSolutionChange}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          >
            {solutions.map((sol) => (
              <option key={sol.id} value={sol.id}>
                {sol.name}
                {sol.code ? ` (${sol.code})` : ''} —{' '}
                {sol.engine_status === 'active'
                  ? 'Engine Active'
                  : 'Engine Pending'}
              </option>
            ))}
          </select>
          {selectedSolution?.engine_status === 'pending' && (
            <p
              style={{
                marginTop: '0.625rem',
                marginBottom: 0,
                fontSize: '0.8rem',
                color: '#92400e',
                backgroundColor: '#fffbeb',
                padding: '0.5rem 0.75rem',
                borderRadius: '0.375rem',
                border: '1px solid #fde68a',
              }}
            >
              <strong>Engine Pending:</strong> Products and pricing can be
              prepared for this solution now. Quotation generation in the Quote
              Wizard remains disabled until its calculation engine is
              implemented.
            </p>
          )}
        </div>

        {canEditMargin && selectedSolution && (
          <div
            style={{
              padding: '1.25rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '0.5rem',
            }}
          >
            <label
              htmlFor="solution-margin-input"
              style={{
                display: 'block',
                fontWeight: 600,
                fontSize: '0.875rem',
                color: '#334155',
                marginBottom: '0.5rem',
              }}
            >
              Solution Default Margin (%)
            </label>
            <form
              onSubmit={handleSaveMargin}
              style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}
            >
              <input
                id="solution-margin-input"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={marginInput}
                onChange={(e) => setMarginInput(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '0.375rem',
                }}
                required
              />
              <button
                type="submit"
                className="btn btn-secondary"
                disabled={isSavingMargin}
              >
                {isSavingMargin ? 'Saving...' : 'Save Margin'}
              </button>
            </form>
            <p
              style={{
                marginTop: '0.5rem',
                marginBottom: 0,
                fontSize: '0.75rem',
                color: '#64748b',
              }}
            >
              Used by the Quote Pricing Engine for margin uplift. Does not
              auto-invent missing product cost prices.
            </p>
          </div>
        )}

        {isAdmin && (
          <div
            style={{
              padding: '1.25rem',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '0.5rem',
            }}
          >
            <div
              style={{
                fontWeight: 600,
                fontSize: '0.875rem',
                color: '#334155',
                marginBottom: '0.5rem',
              }}
            >
              Catalog Entry Cost-Price Policy
            </div>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                cursor: isSavingSettings ? 'wait' : 'pointer',
                fontSize: '0.875rem',
                color: '#1e293b',
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(
                  catalogSettings.catalog_entry_cost_visibility
                )}
                onChange={handleToggleCostVisibility}
                disabled={isSavingSettings}
              />
              <span>
                Allow <strong>Catalog Entry</strong> role to view &amp; edit
                Cost Prices on Catalog screen
              </span>
            </label>
            <p
              style={{
                marginTop: '0.5rem',
                marginBottom: 0,
                fontSize: '0.75rem',
                color: '#64748b',
              }}
            >
              Persisted in PostgreSQL. Internal quote margins and customer
              exports remain strictly protected at all times.
            </p>
          </div>
        )}
      </div>

      {/* Excel Import / Export & Reset Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          padding: '1rem 1.25rem',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '0.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleExportExcel}
            disabled={!selectedSolution}
          >
            Export Catalog (.xlsx)
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleDownloadTemplate}
          >
            Download Starter Template
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            onChange={handleImportFileChange}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={!selectedSolution || isImporting}
          >
            {isImporting ? 'Importing...' : 'Import Excel (.xlsx)'}
          </button>
        </div>

        {selectedSolution?.name === 'WTVision Graphics' && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleResetCatalog}
            style={{ color: '#b45309', borderColor: '#fcd34d' }}
          >
            Reset Shipped Defaults
          </button>
        )}
      </div>

      {/* Search & Filters */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: '0.75rem',
          marginBottom: '1rem',
          padding: '1rem',
          backgroundColor: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '0.5rem',
        }}
      >
        <div>
          <label
            htmlFor="catalog-search-q"
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#475569',
              marginBottom: '0.25rem',
            }}
          >
            Keyword Search
          </label>
          <input
            id="catalog-search-q"
            type="text"
            placeholder="Part, description, brand..."
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            style={{
              width: '100%',
              padding: '0.45rem 0.65rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          />
        </div>
        <div>
          <label
            htmlFor="catalog-filter-part"
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#475569',
              marginBottom: '0.25rem',
            }}
          >
            Part Number
          </label>
          <input
            id="catalog-filter-part"
            type="text"
            placeholder="e.g. PS1050"
            value={partFilter}
            onChange={(e) => setPartFilter(e.target.value)}
            style={{
              width: '100%',
              padding: '0.45rem 0.65rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          />
        </div>
        <div>
          <label
            htmlFor="catalog-filter-brand"
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#475569',
              marginBottom: '0.25rem',
            }}
          >
            Brand
          </label>
          <input
            id="catalog-filter-brand"
            type="text"
            placeholder="e.g. WTVision"
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            style={{
              width: '100%',
              padding: '0.45rem 0.65rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          />
        </div>
        <div>
          <label
            htmlFor="catalog-filter-kind"
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#475569',
              marginBottom: '0.25rem',
            }}
          >
            Product Kind
          </label>
          <select
            id="catalog-filter-kind"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            style={{
              width: '100%',
              padding: '0.45rem 0.65rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          >
            <option value="">All Kinds</option>
            <option value="rule_driven">Rule-Driven (Engine)</option>
            <option value="reference">Reference</option>
          </select>
        </div>
        <div>
          <label
            htmlFor="catalog-filter-price"
            style={{
              display: 'block',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: '#475569',
              marginBottom: '0.25rem',
            }}
          >
            Price Status
          </label>
          <select
            id="catalog-filter-price"
            value={priceStatusFilter}
            onChange={(e) => setPriceStatusFilter(e.target.value)}
            style={{
              width: '100%',
              padding: '0.45rem 0.65rem',
              border: '1px solid #cbd5e1',
              borderRadius: '0.375rem',
            }}
          >
            <option value="ALL">All Items ({items.length})</option>
            <option value="PRICED">Priced</option>
            <option value="UNPRICED">Unpriced (NULL)</option>
          </select>
        </div>
      </div>

      {/* Product Table */}
      <div className="table-container">
        {isLoadingItems ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
            Loading catalog products...
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="state-container">
            <h3>No catalog items found</h3>
            <p>
              Try adjusting your search filters or add a new Reference product.
            </p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID / Lookup Key</th>
                <th>Kind</th>
                <th>Part Number</th>
                <th>Description</th>
                <th>Brand</th>
                <th>Sell Price (USD)</th>
                {canViewCatalogCost && <th>Cost Price (USD)</th>}
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => {
                const isRuleDriven = item.kind === 'rule_driven';
                const isDupPn =
                  item.part_number && duplicatePartNumbers.has(item.part_number);
                return (
                  <tr key={item.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>#{item.id}</div>
                      <code
                        style={{
                          fontSize: '0.7rem',
                          color: '#64748b',
                          backgroundColor: '#f1f5f9',
                          padding: '0.1rem 0.3rem',
                          borderRadius: '0.25rem',
                        }}
                      >
                        {item.lookup_key}
                      </code>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          isRuleDriven ? 'badge-info' : 'badge-neutral'
                        }`}
                      >
                        {isRuleDriven ? 'Rule-Driven' : 'Reference'}
                      </span>
                    </td>
                    <td>
                      {item.part_number ? (
                        <div>
                          <span style={{ fontWeight: 500 }}>
                            {item.part_number}
                          </span>
                          {isDupPn && (
                            <div style={{ marginTop: '0.2rem' }}>
                              <span
                                className="badge badge-warning"
                                style={{ fontSize: '0.65rem' }}
                                title="Shared by multiple items; use ID or Lookup Key when importing via Excel"
                              >
                                Duplicate PN
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span
                          className="badge badge-neutral"
                          title="Database Part Number is NULL"
                        >
                          — (NULL)
                        </span>
                      )}
                    </td>
                    <td style={{ maxWidth: '340px' }}>{item.description}</td>
                    <td>{item.brand || '—'}</td>
                    <td>{formatCurrencyCell(item.sell_price)}</td>
                    {canViewCatalogCost && (
                      <td>{formatCurrencyCell(item.cost_price)}</td>
                    )}
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => openEditProductModal(item)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger"
                          style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => handleDeleteProduct(item)}
                          disabled={isRuleDriven}
                          title={
                            isRuleDriven
                              ? 'Rule-driven items are required by the calculation engine and cannot be deleted'
                              : 'Delete Reference item'
                          }
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Add / Edit Product Modal */}
      {productModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: '0.5rem',
              maxWidth: '520px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15)',
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>
              {editingItem
                ? `Edit Product #${editingItem.id}`
                : 'Add New Reference Product'}
            </h3>
            {editingItem?.kind === 'rule_driven' && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.625rem 0.75rem',
                  backgroundColor: '#eff6ff',
                  border: '1px solid #bfdbfe',
                  borderRadius: '0.375rem',
                  fontSize: '0.8rem',
                  color: '#1e40af',
                }}
              >
                <strong>Rule-Driven Item Protection:</strong> Part Number and
                Kind are bound to the calculation engine and cannot be modified.
                Description, Brand, and Prices may be updated.
              </div>
            )}
            {productModalError && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.625rem 0.75rem',
                  backgroundColor: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '0.375rem',
                  fontSize: '0.85rem',
                  color: '#991b1b',
                }}
              >
                {productModalError}
              </div>
            )}
            <form onSubmit={handleSaveProduct}>
              <div style={{ marginBottom: '0.875rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Part Number (Optional — leave blank for NULL)
                </label>
                <input
                  type="text"
                  value={productForm.part_number}
                  onChange={(e) =>
                    setProductForm({ ...productForm, part_number: e.target.value })
                  }
                  disabled={editingItem?.kind === 'rule_driven'}
                  placeholder="e.g. BDL-REF-100"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                    backgroundColor:
                      editingItem?.kind === 'rule_driven' ? '#f1f5f9' : '#ffffff',
                  }}
                />
              </div>
              <div style={{ marginBottom: '0.875rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Description <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <textarea
                  rows={3}
                  value={productForm.description}
                  onChange={(e) =>
                    setProductForm({ ...productForm, description: e.target.value })
                  }
                  required
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                  }}
                />
              </div>
              <div style={{ marginBottom: '0.875rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Brand
                </label>
                <input
                  type="text"
                  value={productForm.brand}
                  onChange={(e) =>
                    setProductForm({ ...productForm, brand: e.target.value })
                  }
                  placeholder="e.g. WTVision"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                  }}
                />
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: canViewCatalogCost ? '1fr 1fr' : '1fr',
                  gap: '0.75rem',
                  marginBottom: '1.25rem',
                }}
              >
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      marginBottom: '0.25rem',
                    }}
                  >
                    Sell Price (USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={productForm.sell_price}
                    onChange={(e) =>
                      setProductForm({
                        ...productForm,
                        sell_price: e.target.value,
                      })
                    }
                    placeholder="Blank = NULL"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      border: '1px solid #cbd5e1',
                      borderRadius: '0.375rem',
                    }}
                  />
                </div>
                {canViewCatalogCost && (
                  <div>
                    <label
                      style={{
                        display: 'block',
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        marginBottom: '0.25rem',
                      }}
                    >
                      Cost Price (USD)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={productForm.cost_price}
                      onChange={(e) =>
                        setProductForm({
                          ...productForm,
                          cost_price: e.target.value,
                        })
                      }
                      placeholder="Blank = NULL"
                      style={{
                        width: '100%',
                        padding: '0.5rem',
                        border: '1px solid #cbd5e1',
                        borderRadius: '0.375rem',
                      }}
                    />
                  </div>
                )}
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.5rem',
                }}
              >
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setProductModalOpen(false)}
                  disabled={isSavingProduct}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSavingProduct}
                >
                  {isSavingProduct ? 'Saving...' : 'Save Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create / Edit Solution Modal */}
      {solutionModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: '0.5rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15)',
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>
              {solutionModalMode === 'create'
                ? 'Create New Solution'
                : 'Edit Solution'}
            </h3>
            {solutionModalMode === 'create' && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.625rem 0.75rem',
                  backgroundColor: '#fffbeb',
                  border: '1px solid #fde68a',
                  borderRadius: '0.375rem',
                  fontSize: '0.8rem',
                  color: '#92400e',
                }}
              >
                New solutions are created with <strong>Engine Pending</strong>{' '}
                status so you can populate and maintain their product catalog
                immediately while their calculation engine is pending
                implementation.
              </div>
            )}
            {solutionModalError && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.625rem 0.75rem',
                  backgroundColor: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '0.375rem',
                  fontSize: '0.85rem',
                  color: '#991b1b',
                }}
              >
                {solutionModalError}
              </div>
            )}
            <form onSubmit={handleSaveSolution}>
              <div style={{ marginBottom: '0.875rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Solution Name <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <input
                  type="text"
                  value={solutionForm.name}
                  onChange={(e) =>
                    setSolutionForm({ ...solutionForm, name: e.target.value })
                  }
                  disabled={
                    solutionModalMode === 'edit' &&
                    selectedSolution?.name === 'WTVision Graphics'
                  }
                  placeholder="e.g. Ross Video XPression"
                  required
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                  }}
                />
              </div>
              <div style={{ marginBottom: '0.875rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Solution Code (Optional)
                </label>
                <input
                  type="text"
                  value={solutionForm.code}
                  onChange={(e) =>
                    setSolutionForm({ ...solutionForm, code: e.target.value })
                  }
                  placeholder="e.g. ROSS-XPR"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                  }}
                />
              </div>
              <div style={{ marginBottom: '1.25rem' }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    marginBottom: '0.25rem',
                  }}
                >
                  Default Margin (%) <span style={{ color: '#dc2626' }}>*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={solutionForm.default_margin_percent}
                  onChange={(e) =>
                    setSolutionForm({
                      ...solutionForm,
                      default_margin_percent: e.target.value,
                    })
                  }
                  required
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '0.375rem',
                  }}
                />
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: '0.5rem',
                }}
              >
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSolutionModalOpen(false)}
                  disabled={isSavingSolution}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSavingSolution}
                >
                  {isSavingSolution ? 'Saving...' : 'Save Solution'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

