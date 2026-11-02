import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// Top-of-form error banner — for errors that aren't about one specific field
// (e.g. "Wrong email or password" from the login endpoint). Field-specific errors
// go on the TextInput's own `error` prop instead, next to the field they're about.
export function FormError({ message }) {
  const { theme } = useTheme();
  if (!message) return null;

  return (
    <View style={[styles.wrapper, { backgroundColor: theme.colors.danger + '1A', borderColor: theme.colors.danger }]}>
      <Text style={[styles.text, { color: theme.colors.danger }]}>{message}</Text>
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
