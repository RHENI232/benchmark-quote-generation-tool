import { fetchClient } from './client';

export async function getCurrentUser() {
  return fetchClient('/api/users/me');
}

export async function getUsers() {
  return fetchClient('/api/users');
}

export async function inviteUser(email, role_tier) {
  return fetchClient('/api/users/invite', {
    body: { email, role_tier }
  });
}

export async function updateUserRole(userId, role_tier) {
  return fetchClient(`/api/users/${userId}/role`, {
    method: 'PUT',
    body: { role_tier }
  });
}

export async function updateUserStatus(userId, enabled) {
  return fetchClient(`/api/users/${userId}/status`, {
    method: 'PUT',
    body: { enabled }
  });
}

export async function deleteUser(userId) {
  return fetchClient(`/api/users/${userId}`, {
    method: 'DELETE'
  });
}
