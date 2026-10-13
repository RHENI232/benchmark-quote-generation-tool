import { fetchClient } from './client';

export const solutionApi = {
  getSolutions: () => fetchClient('/api/solutions'),
  getSolution: (solutionId) => fetchClient(`/api/solutions/${solutionId}`),
  createSolution: (payload) =>
    fetchClient('/api/solutions', {
      method: 'POST',
      body: payload,
    }),
  updateSolution: (solutionId, payload) =>
    fetchClient(`/api/solutions/${solutionId}`, {
      method: 'PUT',
      body: payload,
    }),
  updateSolutionMargin: (solutionId, defaultMarginPercent) =>
    fetchClient(`/api/solutions/${solutionId}/margin`, {
      method: 'PATCH',
      body: { default_margin_percent: defaultMarginPercent },
    }),
  resetCatalogToDefaults: (solutionId) =>
    fetchClient(`/api/solutions/${solutionId}/catalog/reset`, {
      method: 'POST',
      body: { confirm_reset: true },
    }),
};
