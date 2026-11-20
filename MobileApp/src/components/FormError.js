import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function FormError({ message, tone = 'error' }) {
  const { theme } = useTheme();
  if (!message) return null;
  const color = tone === 'success' ? theme.colors.success : theme.colors.danger;

  return (
    <View style={[styles.wrapper, { backgroundColor: color + '1A', borderColor: color }]}>
      <Text style={[styles.text, { color }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  text: {
    fontSize: 14,
  },
});
