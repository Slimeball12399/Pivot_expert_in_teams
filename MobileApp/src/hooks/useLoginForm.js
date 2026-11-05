import { router } from 'expo-router';
import { useState } from 'react';

import { useAuth } from '../providers/AuthProvider';
import { validateEmail, validatePassword } from '../utils/validators';

// Login logic
export function useLoginForm() {
  const { login } = useAuth();

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
    try {
      await login(email.trim(), password);
      router.replace('/');
    } catch (error) {
      setFormError(error.status === 401 ? 'Wrong email or password.' : 'Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return { email, setEmail, password, setPassword, fieldErrors, formError, submitting, handleSubmit };
}
