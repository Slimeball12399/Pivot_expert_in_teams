import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { LoadErrorState } from '../components/LoadErrorState';
import { ScreenContainer } from '../components/ScreenContainer';
import { Skeleton } from '../components/Skeleton';
import { useBoards } from '../hooks/useBoards';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

const STATUS_LABEL = { online: 'Online', in_session: 'In session', offline: 'Offline' };

function statusColor(status, theme) {
  if (status === 'online') return theme.colors.success;
  if (status === 'in_session') return theme.colors.accent;
  return theme.colors.textSecondary;
}

function BoardRowSkeleton() {
  const { theme } = useTheme();
  return (
    <View style={[styles.row, { backgroundColor: theme.colors.surface }]}>
      <Skeleton width={44} height={44} borderRadius={12} />
      <View style={styles.rowText}>
        <Skeleton width={160} height={16} style={styles.skeletonGapLarge} />
        <Skeleton width={90} height={13} style={styles.skeletonGap} />
        <Skeleton width={120} height={12} />
      </View>
      <Skeleton width={20} height={20} borderRadius={10} />
    </View>
  );
}

function BoardRow({ board, onPress }) {
  const { theme } = useTheme();
  const subtitle = board.status === 'offline' ? `Last seen ${board.lastSeen}` : `Wi-Fi: ${board.wifiName}`;

  return (
    <Pressable
      onPress={onPress}
      style={[styles.row, { backgroundColor: theme.colors.surface }]}
    >
      <View style={[styles.iconBox, { backgroundColor: theme.colors.background }]}>
        <Feather name="cpu" size={22} color={theme.colors.primary} />
      </View>
      <View style={styles.rowText}>
        <Text style={[styles.boardId, { color: theme.colors.text }]}>
          {board.id} <Text style={{ color: theme.colors.textSecondary, fontWeight: '400' }}>· {board.location}</Text>
        </Text>
        <View style={styles.statusLine}>
          <View style={[styles.statusDot, { backgroundColor: statusColor(board.status, theme) }]} />
          <Text style={[styles.statusText, { color: statusColor(board.status, theme) }]}>
            {STATUS_LABEL[board.status]}
          </Text>
        </View>
        <Text style={[styles.subtitle, { color: theme.colors.textSecondary }]}>{subtitle}</Text>
      </View>
      <Feather name="chevron-right" size={20} color={theme.colors.textSecondary} />
    </Pressable>
  );
}

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

      <Modal
        visible={!!selectedBoard}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedBoard(null)}
      >
        <View style={styles.modalRoot}>
          <Pressable style={styles.backdrop} onPress={() => setSelectedBoard(null)} />
          {selectedBoard && (
            <View style={[styles.sheet, { backgroundColor: theme.colors.surface }]}>
              <View style={[styles.handle, { backgroundColor: theme.colors.border }]} />
              <Text style={[styles.sheetTitle, { color: theme.colors.text }]}>
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
                <Feather name="wifi" size={18} color={theme.colors.text} />
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
                <Feather name="target" size={18} color={theme.colors.text} />
                <Text style={[styles.sheetActionText, { color: theme.colors.text }]}>Calibrate</Text>
              </Pressable>

              <Pressable
                disabled={removingId === selectedBoard.id}
                onPress={() => confirmRemove(selectedBoard)}
                style={[styles.sheetAction, styles.sheetActionDanger, { backgroundColor: theme.colors.danger }]}
              >
                <Feather name="trash-2" size={18} color="#ffffff" />
                <Text style={[styles.sheetActionText, { color: '#ffffff' }]}>Remove board</Text>
              </Pressable>

              <Pressable onPress={() => setSelectedBoard(null)} style={styles.cancel}>
                <Text style={[styles.cancelText, { color: theme.colors.text }]}>Cancel</Text>
              </Pressable>
            </View>
          )}
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 },
  subtitleHeader: { fontSize: 14, marginTop: 6 },
  logout: { fontSize: 14, fontWeight: '700', textDecorationLine: 'underline', marginTop: 6 },
  addButton: { marginBottom: 20 },
  centerState: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 60 },
  centerIcon: { opacity: 0.35, marginBottom: 16 },
  centerText: { fontSize: 14, textAlign: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, borderRadius: 16, padding: 14, marginBottom: 12 },
  iconBox: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  rowText: { flex: 1 },
  skeletonGapLarge: { marginBottom: 8 },
  skeletonGap: { marginBottom: 6 },
  boardId: { fontSize: 16, fontWeight: '700' },
  statusLine: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  statusDot: { width: 7, height: 7, borderRadius: 3.5 },
  statusText: { fontSize: 13, fontWeight: '700' },
  subtitle: { fontSize: 12, marginTop: 2 },
  helper: { fontSize: 13, textAlign: 'center', marginTop: 8 },

  modalRoot: { flex: 1 },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)' },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, paddingBottom: 36 },
  handle: { width: 36, height: 4, borderRadius: 2, alignSelf: 'center', marginBottom: 20 },
  sheetTitle: { fontSize: 18, fontWeight: '700', marginBottom: 16 },
  sheetAction: { flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 10 },
  sheetActionDanger: { borderWidth: 0 },
  sheetActionText: { fontSize: 15, fontWeight: '700' },
  cancel: { marginTop: 6, alignItems: 'center' },
  cancelText: { fontSize: 15, fontWeight: '700' },
});
