import { fetchClient } from './client';

export async function getCurrentUser() {
  return fetchClient('/api/users/me');
}
