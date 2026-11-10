import { router } from 'expo-router';
import { useState } from 'react';

import { requestPasswordReset } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';

// Change-password, for an already logged-in user.
export function useChangePasswordForm() {
  const { user, startPasswordReset } = useAuth();
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSendCode() {
    setFormError(null);
    setSubmitting(true);
    try {
      await requestPasswordReset(user.email);
      startPasswordReset(user.email);
      router.push('/(auth)/reset-code');
    } catch (error) {
      if (__DEV__) logRequestError('Request password change code', error);
      setFormError('Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return { email: user?.email ?? '', formError, submitting, handleSendCode };
}
