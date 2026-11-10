import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';

// Placeholder
export function ProgressScreen() {
  const { theme } = useTheme();

  return (
    <ScreenContainer>
      <Text style={theme.styles.text.title}>Progress</Text>
      <Text style={[styles.body, { color: theme.colors.textSecondary }]}>
        Your speech and stability scores will show up here once sessions start being counted.
      </Text>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  body: { marginTop: 12, fontSize: 14, lineHeight: 20 },
});
