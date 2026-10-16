import { fetchClient, API_BASE_URL } from './client';

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

export async function submitQuote(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/submit`, {
    method: 'POST',
    body: payload,
  });
}

export async function approveQuote(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/approve`, {
    method: 'POST',
    body: payload,
  });
}

export async function requestChangesQuote(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/request-changes`, {
    method: 'POST',
    body: payload,
  });
}

export async function overrideApproveQuote(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/override-approve`, {
    method: 'POST',
    body: payload,
  });
}

export async function getApprovalQueue() {
  return fetchClient('/api/quotes/approval-queue');
}

export async function getQuoteHistory(quoteId) {
  return fetchClient(`/api/quotes/${quoteId}/history`);
}

export async function setQuoteUrgency(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/urgent`, {
    method: 'POST',
    body: payload,
  });
}

export async function downloadCustomerPdf(quoteId, quoteRefNo) {
  const token = localStorage.getItem('access_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE_URL}/api/quotes/${quoteId}/export/customer-pdf`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    let errorMsg = 'Failed to download customer PDF.';
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch {
      // Non-JSON error
    }
    const err = new Error(errorMsg);
    err.status = response.status;
    throw err;
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeFilename = quoteRefNo ? `${quoteRefNo}_Customer_Quote.pdf` : `Quote_${quoteId}_Customer_Quote.pdf`;
  a.download = safeFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function refreshQuoteFxRate(quoteId, payload) {
  return fetchClient(`/api/quotes/${quoteId}/refresh-fx`, {
    method: 'POST',
    body: payload,
  });
}
