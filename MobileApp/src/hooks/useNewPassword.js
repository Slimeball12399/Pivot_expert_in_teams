import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';

import { confirmPasswordReset } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';
import { validatePassword } from '../utils/validators';

// sets the new password with the uid/reset_token
export function useNewPassword() {
  const { passwordReset, clearPasswordReset } = useAuth();
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const completingRef = useRef(false);

  useEffect(() => {
    if (!passwordReset?.resetToken && !completingRef.current) {
      router.replace('/(auth)/forgot-password');
    }
  }, [passwordReset]);

  async function handleSubmit() {
    const errors = { password: validatePassword(password) };
    setFieldErrors(errors);
    if (errors.password) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await confirmPasswordReset(passwordReset.uid, passwordReset.resetToken, password);
      completingRef.current = true;
      router.replace('/(auth)/login');
      clearPasswordReset();
    } catch (error) {
      if (__DEV__) logRequestError('Confirm password reset', error);
      if (error.data?.code === 'invalid_token') {
        // Expired/used token — start the whole flow over.
        completingRef.current = true;
        router.replace('/(auth)/forgot-password');
        clearPasswordReset();
        return;
      }
      const backendPasswordError = Array.isArray(error.data?.new_password) ? error.data.new_password[0] : null;
      // The token still works for a weak-password rejection, so let them retry here.
      if (backendPasswordError) {
        setFieldErrors({ password: backendPasswordError });
      } else {
        setFormError('Something went wrong. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return { password, setPassword, fieldErrors, formError, submitting, handleSubmit };
}
