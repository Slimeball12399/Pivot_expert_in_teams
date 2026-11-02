import { Redirect } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';

export default function HomeScreen() {
  const { isAuthenticated } = useAuth();
  const { theme } = useTheme();

  if (isAuthenticated === false) {
    return <Redirect href="/(auth)/login" />;
  }

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
