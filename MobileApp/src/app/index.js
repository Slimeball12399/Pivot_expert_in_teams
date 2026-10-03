import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// `index` is the "/" route, so this screen opens automatically on launch.
export default function HomeScreen() {
  const { theme } = useTheme();

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <Text style={theme.styles.text.title}>Home</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
});
