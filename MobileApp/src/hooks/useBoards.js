import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { fetchBoards, removeBoard } from '../api/boards';

export function useBoards() {
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [removingId, setRemovingId] = useState(null);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        setLoading(true);
        setLoadError(null);
        try {
          const data = await fetchBoards();
          if (!cancelled) setBoards(data);
        } catch {
          if (!cancelled) setLoadError('Could not load boards. Check your connection and try again.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }, []),
  );

  async function remove(boardId) {
    setRemovingId(boardId);
    try {
      await removeBoard(boardId);
      setBoards((prev) => prev.filter((board) => board.id !== boardId));
      return true;
    } catch {
      return false;
    } finally {
      setRemovingId(null);
    }
  }

  return {
    boards,
    loading,
    loadError,
    removingId,
    remove,
  };
}
