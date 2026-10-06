import { fetchClient } from './client';

export async function getQuotes({ skip = 0, limit = 10, clientName = '' }) {
  const params = new URLSearchParams();
  params.append('skip', skip);
  params.append('limit', limit);
  if (clientName) {
    params.append('client_name', clientName);
  }
  return fetchClient(`/api/quotes?${params.toString()}`);
}

export async function getQuote(quoteId) {
  return fetchClient(`/api/quotes/${quoteId}`);
}

export async function previewQuote(payload) {
  return fetchClient('/api/quotes/preview', {
    method: 'POST',
    body: payload,
  });
}

export async function createQuote(payload) {
  return fetchClient('/api/quotes', {
    method: 'POST',
    body: payload,
  });
}

export async function updateQuote(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}`, {
    method: 'PUT',
    body: payload,
  });
}

export async function saveQuoteStatus(quoteId, expectedVersion) {
  return fetchClient(`/api/quotes/${quoteId}/save`, {
    method: 'POST',
    body: { expected_version: expectedVersion },
  });
}
