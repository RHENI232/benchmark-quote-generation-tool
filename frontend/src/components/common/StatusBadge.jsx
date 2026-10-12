import React from 'react';

export default function StatusBadge({ status }) {
  let badgeClass = 'badge-neutral';
  let label = status || 'Unknown';

  if (status) {
    const statusLower = status.toLowerCase();
    if (statusLower === 'approved' || statusLower === 'accepted' || statusLower === 'won') {
      badgeClass = 'badge-success';
      label = 'Approved';
    } else if (statusLower === 'draft') {
      badgeClass = 'badge-warning';
      label = 'Draft';
    } else if (statusLower === 'pending_approval' || statusLower === 'pending') {
      badgeClass = 'badge-warning';
      label = 'Pending Approval';
    } else if (statusLower === 'changes_requested') {
      badgeClass = 'badge-danger';
      label = 'Changes Requested';
    } else if (statusLower === 'rejected' || statusLower === 'lost' || statusLower === 'error') {
      badgeClass = 'badge-danger';
      label = 'Rejected';
    } else if (statusLower === 'sent' || statusLower === 'exported') {
      badgeClass = 'badge-info';
      label = 'Sent';
    } else {
      label = status.toUpperCase().replace('_', ' ');
    }
  }

  return (
    <span className={`badge ${badgeClass}`}>
      {label}
    </span>
  );
}
