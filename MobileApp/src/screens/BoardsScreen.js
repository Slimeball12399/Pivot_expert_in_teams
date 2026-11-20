import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { BoardRow } from '../components/BoardRow';
import { BoardRowSkeleton } from '../components/BoardRowSkeleton';
import { BottomSheet } from '../components/BottomSheet';
import { LoadErrorState } from '../components/LoadErrorState';
import { ScreenContainer } from '../components/ScreenContainer';
import { useBoards } from '../hooks/useBoards';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { onDanger } from '../../assets/styles/colors';

export function BoardsScreen() {
  const { theme } = useTheme();
  const { user, logout } = useAuth();
  const { boards, loading, loadError, removingId, remove } = useBoards();
  const [selectedBoard, setSelectedBoard] = useState(null);

  function confirmRemove(board) {
    setSelectedBoard(null);
    Alert.alert(
      'Remove this board?',
      `${board.id} · ${board.location} will stop appearing in Pivot. You can add it again later.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            const ok = await remove(board.id);
            if (!ok) Alert.alert('Could not remove this board', 'Check your connection and try again.');
          },
        },
      ],
    );
  }

  return (
    <ScreenContainer scroll>
      <View style={styles.header}>
        <View>
          <Text style={theme.styles.text.title}>Boards</Text>
          <Text style={[styles.subtitleHeader, { color: theme.colors.textSecondary }]}>
            {boards.length} boards on {user?.first_name} {user?.last_name}&apos;s account
          </Text>
        </View>
        <Pressable onPress={logout}>
          <Text style={[styles.logout, { color: theme.colors.text }]}>Log out</Text>
        </Pressable>
      </View>

      <Button title="+ Add a board" onPress={() => router.push('/(admin)/boards/add')} style={styles.addButton} />

      {loadError ? (
        <LoadErrorState message={loadError} />
      ) : loading ? (
        <>
          <BoardRowSkeleton />
          <BoardRowSkeleton />
          <BoardRowSkeleton />
        </>
      ) : boards.length === 0 ? (
        <View style={styles.centerState}>
          <Feather name="cpu" size={96} color={theme.colors.textSecondary} style={styles.centerIcon} />
          <Text style={[styles.centerText, { color: theme.colors.textSecondary }]}>
            No boards yet. Add one to get started.
          </Text>
        </View>
      ) : (
        <>
          {boards.map((board) => (
            <BoardRow key={board.id} board={board} onPress={() => setSelectedBoard(board)} />
          ))}
          <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>Tap a board for more options.</Text>
        </>
      )}

      <BottomSheet visible={!!selectedBoard} onClose={() => setSelectedBoard(null)}>
        {selectedBoard && (
          <>
            <Text style={[theme.styles.text.heading, styles.sheetTitle, { color: theme.colors.text }]}>
              {selectedBoard.id} · {selectedBoard.location}
            </Text>

            <Pressable
              onPress={() => {
                const board = selectedBoard;
                setSelectedBoard(null);
                router.push(`/(admin)/boards/${board.id}/wifi`);
              }}
              style={[styles.sheetAction, { borderColor: theme.colors.border }]}
            >
              <Feather name="wifi" size={theme.sizes.icon.inline} color={theme.colors.text} />
              <Text style={[styles.sheetActionText, { color: theme.colors.text }]}>Change Wi-Fi</Text>
            </Pressable>

            <Pressable
              onPress={() => {
                const board = selectedBoard;
                setSelectedBoard(null);
                router.push(`/(admin)/boards/${board.id}/calibrate?location=${encodeURIComponent(board.location)}`);
              }}
              style={[styles.sheetAction, { borderColor: theme.colors.border }]}
            >
              <Feather name="target" size={theme.sizes.icon.inline} color={theme.colors.text} />
              <Text style={[styles.sheetActionText, { color: theme.colors.text }]}>Calibrate</Text>
            </Pressable>

            <Pressable
              disabled={removingId === selectedBoard.id}
              onPress={() => confirmRemove(selectedBoard)}
              style={[styles.sheetAction, styles.sheetActionDanger, { backgroundColor: theme.colors.danger }]}
            >
              <Feather name="trash-2" size={theme.sizes.icon.inline} color={onDanger} />
              <Text style={[styles.sheetActionText, { color: onDanger }]}>Remove board</Text>
            </Pressable>

            <Pressable onPress={() => setSelectedBoard(null)} style={styles.cancel}>
              <Text style={[styles.cancelText, { color: theme.colors.text }]}>Cancel</Text>
            </Pressable>
          </>
        )}
      </BottomSheet>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
  },
  subtitleHeader: {
    fontSize: 14,
    marginTop: 6,
  },
  logout: {
    fontSize: 14,
    fontWeight: '700',
    textDecorationLine: 'underline',
    marginTop: 6,
  },
  addButton: {
    marginBottom: 20,
  },
  centerState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  centerIcon: {
    opacity: 0.35,
    marginBottom: 16,
  },
  centerText: {
    fontSize: 14,
    textAlign: 'center',
  },
  helper: {
    fontSize: 13,
    textAlign: 'center',
    marginTop: 8,
  },

  sheetTitle: {
    marginBottom: 16,
  },
  sheetAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  sheetActionDanger: {
    borderWidth: 0,
  },
  sheetActionText: {
    fontSize: 15,
    fontWeight: '700',
  },
  cancel: {
    marginTop: 6,
    alignItems: 'center',
  },
  cancelText: {
    fontSize: 15,
    fontWeight: '700',
  },
});
