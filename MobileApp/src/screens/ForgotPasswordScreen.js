import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

// SCRUM-60 — UI only. No "forgot password" backend endpoint exists yet..
export function ForgotPasswordScreen() {
  const { theme } = useTheme();
  const [email, setEmail] = useState('');

  return (
    <ScreenContainer>
      <BrandMark subtitle="We'll email you a link to reset your password." />

      <TextInput
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="name@example.com"
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />

      <Button title="Send reset link" onPress={() => {}} style={styles.submit} />

      <Link href="/(auth)/login" style={[styles.link, { color: theme.colors.textSecondary }]}>
        Back to log in
      </Link>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  submit: { marginTop: 8 },
  link: { textAlign: 'center', marginTop: 20, fontSize: 14 },
});
