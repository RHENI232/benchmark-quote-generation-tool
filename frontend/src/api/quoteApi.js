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
