import { API_BASE_URL, fetchClient } from './client';

export const catalogApi = {
  getCatalogSettings: () => fetchClient('/api/catalog/settings'),

  updateCatalogSettings: (catalogEntryCostVisibility) =>
    fetchClient('/api/catalog/settings', {
      method: 'PUT',
      body: { catalog_entry_cost_visibility: catalogEntryCostVisibility },
    }),

  getCatalogItems: ({
    solutionId,
    q = '',
    partNumber = '',
    description = '',
    brand = '',
    kind = '',
  }) => {
    const params = new URLSearchParams();
    params.append('solution_id', solutionId);
    if (q) params.append('q', q);
    if (partNumber) params.append('part_number', partNumber);
    if (description) params.append('description', description);
    if (brand) params.append('brand', brand);
    if (kind) params.append('kind', kind);
    return fetchClient(`/api/catalog?${params.toString()}`);
  },

  createCatalogItem: (payload) =>
    fetchClient('/api/catalog', {
      method: 'POST',
      body: payload,
    }),

  updateCatalogItem: (itemId, payload) =>
    fetchClient(`/api/catalog/${itemId}`, {
      method: 'PUT',
      body: payload,
    }),

  deleteCatalogItem: (itemId) =>
    fetchClient(`/api/catalog/${itemId}`, {
      method: 'DELETE',
    }),

  importCatalogExcel: async (solutionId, file) => {
    const token = localStorage.getItem('access_token');
    const formData = new FormData();
    formData.append('file', file);

    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(
        `${API_BASE_URL}/api/catalog/import?solution_id=${encodeURIComponent(solutionId)}`,
        {
          method: 'POST',
          headers,
          body: formData,
        }
      );
    } catch {
      throw new Error('Network error while uploading Excel file.');
    }

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        window.dispatchEvent(new Event('unauthorized'));
      }
      let errorMsg = 'Excel import failed.';
      let rowErrors = null;
      try {
        const errorData = await response.json();
        if (Array.isArray(errorData.detail)) {
          rowErrors = errorData.detail;
          errorMsg = `Validation failed on ${rowErrors.length} row(s). All changes were rolled back.`;
        } else if (errorData.detail) {
          errorMsg = errorData.detail;
        }
      } catch {
        // Ignore JSON parse error
      }
      const err = new Error(errorMsg);
      if (rowErrors) {
        err.rowErrors = rowErrors;
      }
      throw err;
    }

    return response.json();
  },

  downloadCatalogExport: async (solutionId, solutionCode = '') => {
    const token = localStorage.getItem('access_token');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(
      `${API_BASE_URL}/api/catalog/export?solution_id=${encodeURIComponent(solutionId)}`,
      { method: 'GET', headers }
    );
    if (!response.ok) {
      throw new Error('Failed to export catalog Excel file.');
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeSuffix = (solutionCode || `solution_${solutionId}`).replace(/\s+/g, '_');
    a.download = `catalog_export_${safeSuffix}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  downloadCatalogTemplate: async () => {
    const token = localStorage.getItem('access_token');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(`${API_BASE_URL}/api/catalog/template`, {
      method: 'GET',
      headers,
    });
    if (!response.ok) {
      throw new Error('Failed to download catalog import template.');
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'catalog_import_template.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

