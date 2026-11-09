import { router } from 'expo-router';
import { useState } from 'react';

import { useAuth } from '../providers/AuthProvider';
import { validateEmail, validatePassword } from '../utils/validators';
import { logRequestError } from '../api/client';

// Login logic
export function useLoginForm() {
  const { login, needsVerification } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    const errors = { email: validateEmail(email), password: validatePassword(password) };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    setFormError(null);
    setSubmitting(true);
    const trimmedEmail = email.trim();
    try {
      await login(trimmedEmail, password);
      router.replace('/');
    } catch (error) {
      if (__DEV__) logRequestError('Login', error);
      if (error.data?.code === 'email_not_verified') {
      
        // check-inbox can log in once it's confirmed.
        needsVerification(trimmedEmail, password);
        router.replace('/(auth)/check-inbox');
        return;
      }
      setFormError(error.status === 401 ? 'Wrong email or password.' : 'Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return { email, setEmail, password, setPassword, fieldErrors, formError, submitting, handleSubmit };
}
