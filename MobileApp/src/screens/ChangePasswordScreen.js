import { StyleSheet, Text } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useChangePasswordForm } from '../hooks/useChangePasswordForm';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

export function ChangePasswordScreen() {
  const { theme } = useTheme();
  const { email, formError, submitting, handleSendCode } = useChangePasswordForm();

  return (
    <ScreenContainer>
      <Text style={theme.styles.text.title}>Change password</Text>
      <Text style={[styles.subtitle, { color: theme.colors.textSecondary }]}>
        We&apos;ll email a code to {email} to confirm the change.
      </Text>

      <FormError message={formError} />

      <Button title="Send code" onPress={handleSendCode} loading={submitting} style={styles.submit} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { fontSize: 14, marginTop: 8, marginBottom: 20 },
  submit: { marginTop: 8 },
});
