import { StyleSheet, Text } from 'react-native';

import { BrandMark } from '../components/BrandMark';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { CODE_LENGTH, useCheckInbox } from '../hooks/useCheckInbox';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { CodeInput } from '../ui/CodeInput';
.
export function CheckInboxScreen() {
  const { theme } = useTheme();
  const {
    email,
    code,
    setCode,
    error,
    verifying,
    resending,
    cooldown,
    handleVerify,
    handleResend,
  } = useCheckInbox();

  return (
    <ScreenContainer scroll>
      <BrandMark subtitle={`We sent an ${CODE_LENGTH}-digit code to ${email}.`} />

      <FormError message={error} />

      <CodeInput length={CODE_LENGTH} value={code} onChangeText={setCode} error={error} />

      <Button
        title="Verify"
        onPress={handleVerify}
        loading={verifying}
        disabled={code.length < CODE_LENGTH}
        style={styles.verify}
      />

      <Text
        style={[styles.resend, { color: cooldown > 0 ? theme.colors.textSecondary : theme.colors.text }]}
        onPress={cooldown > 0 || resending ? undefined : handleResend}
      >
        {cooldown > 0 ? `Resend code in ${cooldown}s` : resending ? 'Sending…' : 'Resend code'}
      </Text>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  verify: {
    marginTop: 12,
    marginBottom: 24,
  },
  resend: {
    textAlign: 'center',
    fontSize: 14,
    textDecorationLine: 'underline',
  },
});
