import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';

// Placeholder
export function TrainScreen() {
  const { theme } = useTheme();

  return (
    <ScreenContainer>
      <Text style={theme.styles.text.title}>Training</Text>
      <Text style={[styles.body, { color: theme.colors.textSecondary }]}>
        You&apos;ll be able to join a live session with your trainer from here.
      </Text>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  body: { marginTop: 12, fontSize: 14, lineHeight: 20 },
});
