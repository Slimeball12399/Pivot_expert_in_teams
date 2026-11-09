import { Link } from 'expo-router';
import { StyleSheet } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useForgotPasswordForm } from '../hooks/useForgotPasswordForm';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

export function ForgotPasswordScreen() {
  const { theme } = useTheme();
  const { email, setEmail, fieldErrors, formError, submitting, handleSubmit } = useForgotPasswordForm();

  return (
    <ScreenContainer scroll>
      <BrandMark subtitle="We'll email you a code to reset your password." />

      <FormError message={formError} />

      <TextInput
        label="Email"
        value={email}
        onChangeText={setEmail}
        error={fieldErrors.email}
        placeholder="name@example.com"
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />

      <Button title="Send code" onPress={handleSubmit} loading={submitting} style={styles.submit} />

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
