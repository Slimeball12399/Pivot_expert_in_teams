import { StyleSheet, Text, TextInput as RNTextInput, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function TextInput({ label, value, onChangeText, error, ...inputProps }) {
  const { theme } = useTheme();
  const { colors } = theme;

  return (
    <View style={styles.wrapper}>
      {label && <Text style={[styles.label, { color: colors.text }]}>{label}</Text>}
      <RNTextInput
        value={value}
        onChangeText={onChangeText}
        placeholderTextColor={colors.placeholder}
        style={[
          styles.input,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.danger : colors.border,
            color: colors.text,
          },
        ]}
        {...inputProps}
      />
      {error && <Text style={[styles.error, { color: colors.danger }]}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
  },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 16,
  },
  error: {
    fontSize: 13,
    marginTop: 4,
  },
});
