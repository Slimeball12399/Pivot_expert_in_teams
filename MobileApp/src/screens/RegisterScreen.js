import { Link, router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { Checkbox } from '../ui/Checkbox';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';
import {
  validateBirthDate,
  validateEmail,
  validateHeight,
  validatePassword,
  validatePhone,
} from '../utils/validators';

function firstMessage(value) {
  if (Array.isArray(value)) return value[0];
  return typeof value === 'string' ? value : undefined;
}

// SCRUM-50 + SCRUM-51
export function RegisterScreen() {
  const { theme } = useTheme();
  const { register } = useAuth();

  const [fields, setFields] = useState({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
    phoneNumber: '',
    birthDate: '', 
    heightCm: '',
    improvementGoals: '',
  });
  const [consents, setConsents] = useState({ privacy_notice: false, audio_storage: false, research: false });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function setField(name, value) {
    setFields((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit() {
    const errors = {
      email: validateEmail(fields.email),
      password: validatePassword(fields.password),
      firstName: fields.firstName.trim() ? null : 'Enter your first name.',
      lastName: fields.lastName.trim() ? null : 'Enter your last name.',
      phoneNumber: validatePhone(fields.phoneNumber),
      birthDate: validateBirthDate(fields.birthDate ? new Date(fields.birthDate) : null),
      heightCm: validateHeight(fields.heightCm),
      consents: consents.privacy_notice ? null : 'You must accept the privacy notice.',
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await register({
        ...fields,
        email: fields.email.trim(),
        consents: Object.keys(consents).filter((purpose) => consents[purpose]),
      });
      router.replace('/');
    } catch (error) {
      // Map the backend's field errors 
      // register_speaker) back onto the matching input instead of only
      // handling the duplicate-email case.
      const backendErrors = error.data && typeof error.data === 'object' ? error.data : null;
      const mapped = backendErrors && {
        email: firstMessage(backendErrors.email),
        password: firstMessage(backendErrors.password),
        firstName: firstMessage(backendErrors.first_name),
        lastName: firstMessage(backendErrors.last_name),
        phoneNumber: firstMessage(backendErrors.phone_number),
        birthDate: firstMessage(backendErrors.birth_date),
        heightCm: firstMessage(backendErrors.height_cm),
        consents: firstMessage(backendErrors.consents),
      };

      if (mapped && Object.values(mapped).some(Boolean)) {
        setFieldErrors((prev) => ({ ...prev, ...mapped }));
      } else {
        setFormError('Something went wrong. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

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
        onToggle={(checked) => setConsents((prev) => ({ ...prev, privacy_notice: checked }))}
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
        onToggle={(checked) => setConsents((prev) => ({ ...prev, audio_storage: checked }))}
        label="Allow storing my raw audio recordings"
      />
      <Checkbox
        checked={consents.research}
        onToggle={(checked) => setConsents((prev) => ({ ...prev, research: checked }))}
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
