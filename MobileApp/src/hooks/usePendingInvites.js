import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { fetchInvites } from '../api/invites';

export function usePendingInvites(enabled) {
  const [hasPendingInvites, setHasPendingInvites] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (!enabled) return undefined;
      let cancelled = false;
      (async () => {
        try {
          const invites = await fetchInvites();
          if (!cancelled) setHasPendingInvites(invites.length > 0);
        } catch {
          // badge just won't show
        }
      })();
      return () => { cancelled = true; };
    }, [enabled]),
  );

  return hasPendingInvites;
}
