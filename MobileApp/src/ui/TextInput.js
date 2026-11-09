import { StyleSheet, Text, TextInput as RNTextInput, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// `prefix` is a fixed +45
export function TextInput({ label, value, onChangeText, error, prefix, ...inputProps }) {
  const { theme } = useTheme();
  const { colors } = theme;

  return (
    <View style={styles.wrapper}>
      {label && <Text style={[styles.label, { color: colors.text }]}>{label}</Text>}
      <View
        style={[
          styles.inputRow,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.danger : colors.border,
          },
        ]}
      >
        {prefix && <Text style={[styles.prefix, { color: colors.text }]}>{prefix}</Text>}
        <RNTextInput
          value={value}
          onChangeText={onChangeText}
          placeholderTextColor={colors.placeholder}
          style={[styles.input, { color: colors.text }]}
          {...inputProps}
        />
      </View>
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
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 52,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 16,
  },
  prefix: {
    fontSize: 16,
    marginRight: 6,
  },
  input: {
    flex: 1,
    fontSize: 16,
    paddingVertical: 0,
  },
  error: {
    fontSize: 13,
    marginTop: 4,
  },
});
