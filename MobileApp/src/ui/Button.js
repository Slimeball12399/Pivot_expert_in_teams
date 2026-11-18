import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function Button({ title, onPress, variant = 'primary', disabled = false, loading = false, style }) {
  const { theme } = useTheme();
  const { colors } = theme;
  const isOutline = variant === 'outline';

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        isOutline
          ? { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.primary }
          : { backgroundColor: colors.primary },
        (disabled || loading) && { opacity: 0.5 },
        pressed && !disabled && !loading && { opacity: 0.85 },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isOutline ? colors.primary : colors.primaryText} />
      ) : (
        <Text style={[styles.text, { color: isOutline ? colors.primary : colors.primaryText }]}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  text: {
    fontSize: 16,
    fontWeight: '700',
  },
});
