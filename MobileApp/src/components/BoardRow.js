import { Feather } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

const STATUS_LABEL = { online: 'Online', in_session: 'In session', offline: 'Offline' };

function statusColor(status, theme) {
  if (status === 'online') return theme.colors.success;
  if (status === 'in_session') return theme.colors.accent;
  return theme.colors.textSecondary;
}

export function BoardRow({ board, onPress }) {
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

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
  },
  iconBox: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: {
    flex: 1,
  },
  boardId: {
    fontSize: 16,
    fontWeight: '700',
  },
  statusLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
});
