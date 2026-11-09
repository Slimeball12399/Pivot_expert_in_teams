import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';

import { resendVerificationCode, verifyEmail } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';

export const CODE_LENGTH = 8;
// Matches the backend's EMAIL_CODE_RESEND_COOLDOWN. 
const RESEND_COOLDOWN_SECONDS = 60;

// Owns CheckInboxScreen's state: the code input, verifying it, and resending.
export function useCheckInbox() {
  const { pendingVerification, login, clearVerification } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);

  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);

  const completingRef = useRef(false);

  useEffect(() => {
    if (!pendingVerification && !completingRef.current) router.replace('/(auth)/login');
  }, [pendingVerification]);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const id = setInterval(() => setCooldown((seconds) => Math.max(0, seconds - 1)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  async function handleVerify() {
    if (!pendingVerification || code.length !== CODE_LENGTH) return;
    setError(null);
    setVerifying(true);
    try {
      await verifyEmail(pendingVerification.email, code);
      await login(pendingVerification.email, pendingVerification.password);
      completingRef.current = true;
      router.replace('/');
      clearVerification();
    } catch (err) {
      if (__DEV__) logRequestError('Verify email', err);
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
    if (!pendingVerification || cooldown > 0) return;
    setResending(true);
    try {
      await resendVerificationCode(pendingVerification.email);
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      if (__DEV__) logRequestError('Resend code', err);
    } finally {
      setResending(false);
    }
  }

  return {
    email: pendingVerification?.email ?? '',
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
