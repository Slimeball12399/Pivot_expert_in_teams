import { Link, router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';
import { validateEmail, validatePassword } from '../utils/validators';

// SCRUM-52. Logs in, then hands off to index.js's auth redirect.
export function LoginScreen() {
  const { theme } = useTheme();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    const errors = { email: validateEmail(email), password: validatePassword(password) };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      router.replace('/');
    } catch (error) {
      setFormError(error.status === 401 ? 'Wrong email or password.' : 'Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ScreenContainer>
      <Text style={[theme.styles.text.title, styles.title]}>Log in</Text>

      <FormError message={formError} />

      <TextInput
        label="Email"
        value={email}
        onChangeText={setEmail}
        error={fieldErrors.email}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      <TextInput
        label="Password"
        value={password}
        onChangeText={setPassword}
        error={fieldErrors.password}
        secureTextEntry
        autoComplete="password"
      />

      <Button title="Log in" onPress={handleSubmit} loading={submitting} style={styles.submit} />

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
