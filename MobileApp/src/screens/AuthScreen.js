import { Link } from 'expo-router';
import { useState } from 'react';
import { LayoutAnimation, StyleSheet, Text } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useLoginForm } from '../hooks/useLoginForm';
import { useRegisterForm } from '../hooks/useRegisterForm';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { SegmentedControl } from '../ui/SegmentedControl';
import { TextInput } from '../ui/TextInput';

const TABS = [
  { label: 'Log in', value: 'login' },
  { label: 'Register', value: 'register' },
];

export function AuthScreen({ tab: initialTab }) {
  const { theme } = useTheme();
  const loginForm = useLoginForm();
  const registerForm = useRegisterForm();
  const [tab, setTab] = useState(initialTab);
  const isLogin = tab === 'login';

  function switchTab(next) {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setTab(next);
  }

  return (
    <ScreenContainer scroll>
      <BrandMark subtitle="Train your balance and your voice together." />

      <SegmentedControl options={TABS} value={tab} onChange={switchTab} />

      {isLogin ? (
        <>
          <FormError message={loginForm.formError} />

          <TextInput
            label="Email"
            value={loginForm.email}
            onChangeText={loginForm.setEmail}
            error={loginForm.fieldErrors.email}
            placeholder="name@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
          />
          <TextInput
            label="Password"
            value={loginForm.password}
            onChangeText={loginForm.setPassword}
            error={loginForm.fieldErrors.password}
            placeholder="At least 8 characters"
            secureTextEntry
            autoComplete="password"
          />

          <Link href="/(auth)/forgot-password" style={[styles.forgot, { color: theme.colors.text }]}>
            Forgot password?
          </Link>

          <Button title="Log in" onPress={loginForm.handleSubmit} loading={loginForm.submitting} style={styles.submit} />

          <Text style={[styles.footerLine, { color: theme.colors.textSecondary }]}>
            New here?{' '}
            <Text style={[styles.footerLink, { color: theme.colors.text }]} onPress={() => switchTab('register')}>
              Create an account
            </Text>
          </Text>
        </>
      ) : (
        <>
          <FormError message={registerForm.formError} />

          <TextInput
            label="First name"
            value={registerForm.fields.firstName}
            onChangeText={(v) => registerForm.setField('firstName', v)}
            error={registerForm.fieldErrors.firstName}
            placeholder="e.g. Maja"
          />
          <TextInput
            label="Last name"
            value={registerForm.fields.lastName}
            onChangeText={(v) => registerForm.setField('lastName', v)}
            error={registerForm.fieldErrors.lastName}
            placeholder="e.g. Holm"
          />
          <TextInput
            label="Email"
            value={registerForm.fields.email}
            onChangeText={(v) => registerForm.setField('email', v)}
            error={registerForm.fieldErrors.email}
            placeholder="name@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
          />
          <TextInput
            label="Password"
            value={registerForm.fields.password}
            onChangeText={(v) => registerForm.setField('password', v)}
            error={registerForm.fieldErrors.password}
            placeholder="At least 8 characters"
            secureTextEntry
          />
          <TextInput
            label="Phone number"
            value={registerForm.fields.phoneNumber}
            onChangeText={(v) => registerForm.setField('phoneNumber', v)}
            error={registerForm.fieldErrors.phoneNumber}
            prefix="+45"
            placeholder="e.g. 12345678"
            keyboardType="phone-pad"
          />
          <TextInput
            label="Date of birth"
            value={registerForm.fields.birthDate}
            onChangeText={(v) => registerForm.setField('birthDate', v)}
            error={registerForm.fieldErrors.birthDate}
            placeholder="DD/MM/YYYY"
          />
          <TextInput
            label="Height (cm)"
            value={registerForm.fields.heightCm}
            onChangeText={(v) => registerForm.setField('heightCm', v)}
            error={registerForm.fieldErrors.heightCm}
            placeholder="e.g. 170"
            keyboardType="number-pad"
          />
          <TextInput
            label="Improvement goals (optional)"
            value={registerForm.fields.improvementGoals}
            onChangeText={(v) => registerForm.setField('improvementGoals', v)}
            placeholder="e.g. Project more during presentations"
          />

          <Checkbox
            checked={registerForm.consents.privacy_notice}
            onToggle={(checked) => registerForm.toggleConsent('privacy_notice', checked)}
            label="I accept the Privacy Notice"
            required
          />
          {registerForm.fieldErrors.consents && (
            <Text style={[styles.consentError, { color: theme.colors.danger }]}>
              {registerForm.fieldErrors.consents}
            </Text>
          )}
          <Checkbox
            checked={registerForm.consents.audio_storage}
            onToggle={(checked) => registerForm.toggleConsent('audio_storage', checked)}
            label="Allow storing my raw audio recordings"
          />
          <Checkbox
            checked={registerForm.consents.research}
            onToggle={(checked) => registerForm.toggleConsent('research', checked)}
            label="Allow using my data for Pivot research"
          />

          <Button
            title="Register"
            onPress={registerForm.handleSubmit}
            loading={registerForm.submitting}
            style={styles.submit}
          />

          <Text style={[styles.footerLine, { color: theme.colors.textSecondary }]}>
            Already have an account?{' '}
            <Text style={[styles.footerLink, { color: theme.colors.text }]} onPress={() => switchTab('login')}>
              Log in
            </Text>
          </Text>
        </>
      )}

      <Text style={[styles.gdpr, { color: theme.colors.textSecondary }]}>
        Your voice and balance data are stored in the EU and only shared with your trainer.{' '}
        <Link href="/(auth)/privacy-notice" style={[styles.gdprLink, { color: theme.colors.textSecondary }]}>
          How we handle your data
        </Link>
      </Text>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  forgot: { textAlign: 'right', marginBottom: 16, fontSize: 13, textDecorationLine: 'underline' },
  submit: { marginTop: 4, marginBottom: 20 },
  footerLine: { textAlign: 'center', fontSize: 14 },
  footerLink: { fontWeight: '700', textDecorationLine: 'underline' },
  consentError: { fontSize: 13, marginTop: -8, marginBottom: 12 },
  gdpr: { textAlign: 'center', fontSize: 12, marginTop: 28, lineHeight: 18 },
  gdprLink: { textDecorationLine: 'underline' },
});
