// MOCK — SCRUM-57's backend doesn't exist yet

let mockInvites = [
  { id: '1', trainerName: 'Jonas Berg', expiresAt: '2026-11-24' },
  { id: '2', trainerName: 'Mette Lund', expiresAt: '2026-11-30' },
];
let mockCurrentTrainer = 'Anna Pedersen';

function delay(ms = 500) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchInvites() {
  await delay();
  return { invites: mockInvites, currentTrainer: mockCurrentTrainer };
}

export async function acceptInvite(id) {
  await delay();
  const invite = mockInvites.find((item) => item.id === id);
  if (!invite) throw new Error('Invite not found');
  mockCurrentTrainer = invite.trainerName;
  mockInvites = mockInvites.filter((item) => item.id !== id);
  return { trainerName: invite.trainerName };
}
