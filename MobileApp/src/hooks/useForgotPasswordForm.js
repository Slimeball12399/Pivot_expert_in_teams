import { router } from 'expo-router';
import { useState } from 'react';

import { requestPasswordReset } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';
import { validateEmail } from '../utils/validators';

// forgot-password: email in, a reset code emailed out.
export function useForgotPasswordForm() {
  const { startPasswordReset } = useAuth();
  const [email, setEmail] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    const errors = { email: validateEmail(email) };
    setFieldErrors(errors);
    if (errors.email) return;

    setFormError(null);
    setSubmitting(true);
    const trimmedEmail = email.trim();
    try {
      await requestPasswordReset(trimmedEmail);
      startPasswordReset(trimmedEmail);
      router.replace('/(auth)/reset-code');
    } catch (error) {
      if (__DEV__) logRequestError('Request password reset', error);
      setFormError('Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return { email, setEmail, fieldErrors, formError, submitting, handleSubmit };
}
