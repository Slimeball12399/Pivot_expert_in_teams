import { apiRequest } from './client';

function fullName(person) {
  return person ? `${person.first_name} ${person.last_name}`.trim() : null;
}

function mapInvite(raw) {
  return {
    id: raw.id,
    trainerName: fullName(raw.trainer),
    expiresAt: raw.expires_at,
    replacesTrainerName: fullName(raw.replaces_trainer),
  };
}

// GET /api/invites/ — the speaker's open invitations, newest first.
export async function fetchInvites() {
  const data = await apiRequest('/invites/');
  return data.map(mapInvite);
}

// POST /api/invites/<id>/accept/
export async function acceptInvite(id) {
  const data = await apiRequest(`/invites/${id}/accept/`, { method: 'POST' });
  return { trainerName: fullName(data.trainer), previousTrainerName: fullName(data.previous_trainer) };
}

// POST /api/invites/<id>/decline/
export function declineInvite(id) {
  return apiRequest(`/invites/${id}/decline/`, { method: 'POST' });
}
