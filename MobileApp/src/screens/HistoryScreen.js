import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';

export function HistoryScreen() {
  const { theme } = useTheme();

  return (
    <ScreenContainer>
      <Text style={theme.styles.text.title}>Sessions</Text>
      <Text style={[styles.body, { color: theme.colors.textSecondary }]}>
        Your past sessions will show up here once you&apos;ve trained.
      </Text>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  body: { marginTop: 12, fontSize: 14, lineHeight: 20 },
});
