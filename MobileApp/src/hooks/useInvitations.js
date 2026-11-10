import { useEffect, useState } from 'react';

import { acceptInvite, fetchInvites } from '../api/invites';

export function useInvitations() {
  const [invites, setInvites] = useState([]);
  const [currentTrainer, setCurrentTrainer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [acceptingId, setAcceptingId] = useState(null);
  const [acceptError, setAcceptError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const data = await fetchInvites();
        setInvites(data.invites);
        setCurrentTrainer(data.currentTrainer);
      } catch {
        setLoadError('Could not load invitations. Try again.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Returns whether it succeeded, so the sheet knows whether to close itself.
  async function accept(invite) {
    setAcceptingId(invite.id);
    setAcceptError(null);
    try {
      await acceptInvite(invite.id);
      setInvites((prev) => prev.filter((item) => item.id !== invite.id));
      setCurrentTrainer(invite.trainerName);
      setSuccessMessage(`You're now linked to ${invite.trainerName}.`);
      return true;
    } catch {
      setAcceptError('Could not accept this invitation. Try again.');
      return false;
    } finally {
      setAcceptingId(null);
    }
  }

  function clearAcceptError() {
    setAcceptError(null);
  }

  return {
    invites, currentTrainer, loading, loadError,
    acceptingId, acceptError, successMessage, accept, clearAcceptError,
  };
}
