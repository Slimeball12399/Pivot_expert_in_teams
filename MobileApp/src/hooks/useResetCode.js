import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { requestPasswordReset, verifyPasswordResetCode } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';

export const CODE_LENGTH = 8;
const RESEND_COOLDOWN_SECONDS = 60;

export function useResetCode() {
  const { passwordReset, setPasswordResetToken } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);

  useEffect(() => {
    if (!passwordReset) router.replace('/(auth)/forgot-password');
  }, [passwordReset]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setInterval(() => setCooldown((seconds) => Math.max(0, seconds - 1)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  async function handleVerify() {
    if (!passwordReset || code.length !== CODE_LENGTH) return;
    setError(null);
    setVerifying(true);
    try {
      const { uid, reset_token: resetToken } = await verifyPasswordResetCode(passwordReset.email, code);
      // Set before navigating, so new-password's own guard sees the token
      // already in place instead of a momentarily-stale passwordReset.
      setPasswordResetToken(uid, resetToken);
      router.replace('/(auth)/new-password');
    } catch (err) {
      if (__DEV__) logRequestError('Verify reset code', err);
      setError(
        err.data?.code === 'invalid_code'
          ? 'That code is wrong or has expired. Check the email or ask for a new code.'
          : 'Something went wrong. Try again.',
      );
    } finally {
      setVerifying(false);
    }
  }

  async function handleResend() {
    if (!passwordReset || cooldown > 0) return;
    setResending(true);
    try {
      await requestPasswordReset(passwordReset.email);
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      if (__DEV__) logRequestError('Resend reset code', err);
    } finally {
      setResending(false);
    }
  }

  return {
    email: passwordReset?.email ?? '',
    code,
    setCode,
    error,
    verifying,
    resending,
    cooldown,
    handleVerify,
    handleResend,
  };
}
