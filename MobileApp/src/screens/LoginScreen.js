import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

// SCRUM-52 — layout only for now. Submit handler, validation, and the
// useAuth() hook.
export function LoginScreen() {
  const { theme } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <ScreenContainer>
      <Text style={[theme.styles.text.title, styles.title]}>Log in</Text>

      <TextInput
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      <TextInput label="Password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" />

      <Button title="Log in" onPress={() => {}} style={styles.submit} />

      <Link href="/(auth)/register" style={[styles.link, { color: theme.colors.textSecondary }]}>
        Don&apos;t have an account? Register
      </Link>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginBottom: 24 },
  submit: { marginTop: 8 },
  link: { textAlign: 'center', marginTop: 20, fontSize: 14 },
});
