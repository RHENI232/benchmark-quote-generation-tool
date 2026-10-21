export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchClient(endpoint, { body, ...customConfig } = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
  };

  // Only apply cache-busting to GET requests to prevent unnecessary preflight overhead
  if (!body && customConfig.method !== 'POST') {
    headers['Cache-Control'] = 'no-cache';
    headers['Pragma'] = 'no-cache';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    method: body ? 'POST' : 'GET',
    ...customConfig,
    headers: {
      ...headers,
      ...customConfig.headers,
    },
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, config);
  } catch (error) {
    const netError = new Error('Network error. Please check your connection and try again.');
    netError.status = 0;
    netError.isNetworkError = true;
    netError.originalError = error;
    throw netError;
  }

  if (!response.ok) {
    let errorMsg = 'An error occurred';
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        if (Array.isArray(errorData.detail)) {
          errorMsg = JSON.stringify(errorData.detail);
        } else {
          errorMsg = errorData.detail;
        }
      }
    } catch {
      if (response.statusText) {
        errorMsg = response.statusText;
      }
    }

    if (
      response.status === 401 ||
      (response.status === 403 && (errorMsg === 'Not authenticated' || errorMsg.toLowerCase().includes('credential')))
    ) {
      // Token is invalid/expired - clear it
      localStorage.removeItem('access_token');
      // Dispatch unauthorized event to notify AuthContext to update auth state
      window.dispatchEvent(new Event('unauthorized'));
    }

    const error = new Error(errorMsg);
    error.status = response.status;
    error.detail = errorMsg;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
