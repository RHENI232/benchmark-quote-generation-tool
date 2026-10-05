export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchClient(endpoint, { body, ...customConfig } = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
  };

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
    throw new Error('Network error. Please try again.');
  }

  if (!response.ok) {
    if (response.status === 401) {
      // Token is invalid/expired - clear it
      localStorage.removeItem('access_token');
      // A full page reload will trigger the route guard to redirect to /login
      window.dispatchEvent(new Event('unauthorized'));
    }

    let errorMsg = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMsg = errorData.detail || errorMsg;
    } catch (e) {
      // Failed to parse JSON error
    }
    throw new Error(errorMsg);
  }

  return response.json();
}
