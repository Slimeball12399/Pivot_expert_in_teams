import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';

// Placeholder
export function UserDetailScreen({ userId }) {
  const { theme } = useTheme();

  return (
    <ScreenContainer>
      <Text style={theme.styles.text.title}>User profile</Text>
      <Text style={[styles.body, { color: theme.colors.textSecondary }]}>
        Details for this user aren&apos;t available yet. This screen will show their charts and session history.
      </Text>
      {__DEV__ && <Text style={[styles.body, { color: theme.colors.textSecondary }]}>User ID: {userId}</Text>}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  body: { marginTop: 12, fontSize: 14, lineHeight: 20 },
});
