import { fetchClient } from './client';

export async function login(email, password) {
  return fetchClient('/api/auth/login', {
    method: 'POST',
    body: { email, password }
  });
}
