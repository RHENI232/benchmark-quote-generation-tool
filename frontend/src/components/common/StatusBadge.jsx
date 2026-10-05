import React from 'react';

export default function StatusBadge({ status }) {
  let badgeClass = 'badge-neutral';

  if (status) {
    const statusLower = status.toLowerCase();
    if (statusLower === 'approved' || statusLower === 'accepted' || statusLower === 'won') {
      badgeClass = 'badge-success';
    } else if (statusLower === 'draft' || statusLower === 'pending') {
      badgeClass = 'badge-warning';
    } else if (statusLower === 'rejected' || statusLower === 'lost' || statusLower === 'error') {
      badgeClass = 'badge-danger';
    } else if (statusLower === 'sent' || statusLower === 'exported') {
      badgeClass = 'badge-info';
    }
  }

  return (
    <span className={`badge ${badgeClass}`}>
      {status || 'Unknown'}
    </span>
  );
}
