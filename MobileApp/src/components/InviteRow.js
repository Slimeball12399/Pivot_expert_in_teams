import { Feather } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { formatExpiry } from '../utils/format';

export function InviteRow({ invite, onPress }) {
  const { theme } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={[styles.card, styles.row, { backgroundColor: theme.colors.surface }]}
    >
      <View>
        <Text style={[styles.trainerName, { color: theme.colors.text }]}>{invite.trainerName}</Text>
        <Text style={[styles.expiry, { color: theme.colors.textSecondary }]}>
          Expires {formatExpiry(invite.expiresAt)}
        </Text>
      </View>
      <Feather name="chevron-right" size={20} color={theme.colors.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    padding: 20,
    marginTop: 20,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  trainerName: {
    fontSize: 18,
    fontWeight: '700',
  },
  expiry: {
    fontSize: 13,
    marginTop: 4,
  },
});
