import { Feather } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// A step-progress pill
export function StatusPill({ state, label }) {
  const { theme } = useTheme();
  const done = state === 'done';
  const active = state === 'active';

  const containerStyle = done
    ? { backgroundColor: theme.colors.success + '26' }
    : { borderWidth: 1, borderColor: active ? theme.colors.primary : theme.colors.border };

  const textColor = done ? theme.colors.success : active ? theme.colors.text : theme.colors.textSecondary;

  return (
    <View style={[styles.pill, containerStyle]}>
      {done && <Feather name="check" size={14} color={theme.colors.success} />}
      <Text style={[styles.pillText, { color: textColor }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12 },
  pillText: { fontSize: 13, fontWeight: '700' },
});
