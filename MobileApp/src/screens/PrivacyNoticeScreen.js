import { router } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

// SCRUM-51. Read-only .. Placeholder..
export function PrivacyNoticeScreen() {
  const { theme } = useTheme();

  return (
    <ScreenContainer scroll>
      <Text style={[theme.styles.text.title, styles.title]}>Privacy Notice</Text>
      <Text style={[theme.styles.text.body, { color: theme.colors.textSecondary }]}>
        PLACEHOLDER — replace with Pivot&apos;s actual privacy notice text before release.
        explain what data Pivot collects (account details, balance-board session data, optionally raw
        audio), why, how long it&apos;s kept, and the user&apos;s GDPR rights.
      </Text>
      <Button title="Close" variant="outline" onPress={() => router.back()} style={styles.close} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginBottom: 16 },
  close: { marginTop: 24 },
});
