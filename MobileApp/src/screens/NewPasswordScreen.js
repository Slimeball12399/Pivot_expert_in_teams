import { StyleSheet } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useNewPassword } from '../hooks/useNewPassword';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

// set a new password with the code already confirmed.
export function NewPasswordScreen() {
  const { password, setPassword, fieldErrors, formError, submitting, handleSubmit } = useNewPassword();

  return (
    <ScreenContainer scroll>
      <BrandMark subtitle="Choose a new password." />

      <FormError message={formError} />

      <TextInput
        label="New password"
        value={password}
        onChangeText={setPassword}
        error={fieldErrors.password}
        placeholder="At least 8 characters"
        secureTextEntry
        autoComplete="password-new"
      />

      <Button title="Reset password" onPress={handleSubmit} loading={submitting} style={styles.submit} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  submit: { marginTop: 8 },
});
