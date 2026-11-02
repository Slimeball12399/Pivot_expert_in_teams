import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useLoginForm } from '../hooks/useLoginForm';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

//State and submit logic live in useLoginForm().
export function LoginScreen() {
  const { theme } = useTheme();
  const { email, setEmail, password, setPassword, fieldErrors, formError, submitting, handleSubmit } =
    useLoginForm();

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
