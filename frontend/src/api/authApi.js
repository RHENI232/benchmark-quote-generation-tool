import { fetchClient } from './client';

export async function login(email, password) {
  return fetchClient('/api/auth/login', {
    method: 'POST',
    body: { email, password }
  });
}

export async function acceptInvite(token, new_password) {
  return fetchClient('/api/auth/invite/accept', {
    method: 'POST',
    body: { token, new_password }
  });
}
