import { Feather } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function LoadErrorState({ message, icon = 'wifi-off' }) {
  const { theme } = useTheme();
  return (
    <View style={styles.wrap}>
      <Feather name={icon} size={96} color={theme.colors.textSecondary} style={styles.icon} />
      <Text style={[styles.text, { color: theme.colors.textSecondary }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 60 },
  icon: { opacity: 0.35, marginBottom: 16 },
  text: { fontSize: 14, textAlign: 'center' },
});
