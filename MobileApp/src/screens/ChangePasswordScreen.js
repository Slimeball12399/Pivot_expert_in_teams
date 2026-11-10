import { StyleSheet } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useChangePasswordForm } from '../hooks/useChangePasswordForm';
import { Button } from '../ui/Button';

export function ChangePasswordScreen() {
  const { email, formError, submitting, handleSendCode } = useChangePasswordForm();

  return (
    <ScreenContainer>
      <BrandMark subtitle={`We'll email a code to ${email} to confirm the change.`} />

      <FormError message={formError} />

      <Button title="Send code" onPress={handleSendCode} loading={submitting} style={styles.submit} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  submit: { marginTop: 8 },
});
