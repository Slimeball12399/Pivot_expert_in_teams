import { Link } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useRegisterForm } from '../hooks/useRegisterForm';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { TextInput } from '../ui/TextInput';

//registration + privacy-notice consent.
export function RegisterScreen() {
  const { theme } = useTheme();
  const { fields, setField, consents, toggleConsent, fieldErrors, formError, submitting, handleSubmit } =
    useRegisterForm();

  return (
    <ScreenContainer scroll>
      <Text style={[theme.styles.text.title, styles.title]}>Create account</Text>

      <FormError message={formError} />

      <TextInput label="First name" value={fields.firstName} onChangeText={(v) => setField('firstName', v)} error={fieldErrors.firstName} />
      <TextInput label="Last name" value={fields.lastName} onChangeText={(v) => setField('lastName', v)} error={fieldErrors.lastName} />
      <TextInput
        label="Email"
        value={fields.email}
        onChangeText={(v) => setField('email', v)}
        error={fieldErrors.email}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      <TextInput
        label="Password"
        value={fields.password}
        onChangeText={(v) => setField('password', v)}
        error={fieldErrors.password}
        secureTextEntry
      />
      <TextInput
        label="Phone number"
        value={fields.phoneNumber}
        onChangeText={(v) => setField('phoneNumber', v)}
        error={fieldErrors.phoneNumber}
        placeholder="e.g. 12345678"
        keyboardType="phone-pad"
      />
      <TextInput
        label="Date of birth"
        value={fields.birthDate}
        onChangeText={(v) => setField('birthDate', v)}
        error={fieldErrors.birthDate}
        placeholder="YYYY-MM-DD"
      />
      <TextInput
        label="Height (cm)"
        value={fields.heightCm}
        onChangeText={(v) => setField('heightCm', v)}
        error={fieldErrors.heightCm}
        keyboardType="number-pad"
      />
      <TextInput
        label="Improvement goals (optional)"
        value={fields.improvementGoals}
        onChangeText={(v) => setField('improvementGoals', v)}
      />

      <Checkbox
        checked={consents.privacy_notice}
        onToggle={(checked) => toggleConsent('privacy_notice', checked)}
        label="I accept the Privacy Notice"
      />
      {fieldErrors.consents && (
        <Text style={[styles.consentError, { color: theme.colors.danger }]}>{fieldErrors.consents}</Text>
      )}
      <Link href="/(auth)/privacy-notice" style={[styles.link, { color: theme.colors.textSecondary }]}>
        View Privacy Notice
      </Link>

      <Checkbox
        checked={consents.audio_storage}
        onToggle={(checked) => toggleConsent('audio_storage', checked)}
        label="Allow storing my raw audio recordings"
      />
      <Checkbox
        checked={consents.research}
        onToggle={(checked) => toggleConsent('research', checked)}
        label="Allow using my data for Pivot research"
      />

      <Button title="Register" onPress={handleSubmit} loading={submitting} style={styles.submit} />

      <Link href="/(auth)/login" style={[styles.link, { color: theme.colors.textSecondary }]}>
        Already have an account? Log in
      </Link>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginBottom: 24 },
  submit: { marginTop: 8 },
  link: { textAlign: 'center', marginVertical: 12, fontSize: 14 },
  consentError: { fontSize: 13, marginTop: -8, marginBottom: 12 },
});
