import { useEffect, useState } from 'react';

import { me } from '../api/auth';
import { acceptInvite, fetchInvites } from '../api/invites';

export function useInvitations() {
  const [invites, setInvites] = useState([]);
  const [currentTrainer, setCurrentTrainer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [acceptingId, setAcceptingId] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const [invitesData, meData] = await Promise.all([fetchInvites(), me()]);
        setInvites(invitesData);
        const trainer = meData.profile?.trainer;
        setCurrentTrainer(trainer ? `${trainer.first_name} ${trainer.last_name}`.trim() : null);
      } catch {
        setLoadError('Could not load invitations. Try again.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Returns { ok, message }, so the screen can alert the result either way.
  async function accept(invite) {
    setAcceptingId(invite.id);
    try {
      const result = await acceptInvite(invite.id);
      setInvites((prev) => prev.filter((item) => item.id !== invite.id));
      setCurrentTrainer(result.trainerName);
      return { ok: true, message: `You're now linked to ${result.trainerName}.` };
    } catch {
      return { ok: false, message: 'Check your connection and try again.' };
    } finally {
      setAcceptingId(null);
    }
  }

  return { invites, currentTrainer, loading, loadError, acceptingId, accept };
}
