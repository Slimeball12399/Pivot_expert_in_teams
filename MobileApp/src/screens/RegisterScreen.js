import { Link } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';

import { ScreenContainer } from '../components/ScreenContainer';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { TextInput } from '../ui/TextInput';

// SCRUM-50 (registration) + SCRUM-51 (privacy-notice consent) — layout only
export function RegisterScreen() {
  const { theme } = useTheme();
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

  function setField(name, value) {
    setFields((prev) => ({ ...prev, [name]: value }));
  }

  return (
    <ScreenContainer scroll>
      <Text style={[theme.styles.text.title, styles.title]}>Create account</Text>

      <TextInput label="First name" value={fields.firstName} onChangeText={(v) => setField('firstName', v)} />
      <TextInput label="Last name" value={fields.lastName} onChangeText={(v) => setField('lastName', v)} />
      <TextInput
        label="Email"
        value={fields.email}
        onChangeText={(v) => setField('email', v)}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      <TextInput label="Password" value={fields.password} onChangeText={(v) => setField('password', v)} secureTextEntry />
      <TextInput
        label="Phone number"
        value={fields.phoneNumber}
        onChangeText={(v) => setField('phoneNumber', v)}
        placeholder="e.g. 12345678"
        keyboardType="phone-pad"
      />
      <TextInput
        label="Date of birth"
        value={fields.birthDate}
        onChangeText={(v) => setField('birthDate', v)}
        placeholder="YYYY-MM-DD"
      />
      <TextInput
        label="Height (cm)"
        value={fields.heightCm}
        onChangeText={(v) => setField('heightCm', v)}
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

      <Button title="Register" onPress={() => {}} style={styles.submit} />

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
});
