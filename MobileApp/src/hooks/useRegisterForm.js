import { router } from 'expo-router';
import { useState } from 'react';

import { useAuth } from '../providers/AuthProvider';
import {
  toIsoBirthDate,
  validateBirthDate,
  validateEmail,
  validateHeight,
  validatePassword,
  validatePhone,
} from '../utils/validators';
import { logRequestError } from '../api/client';

function firstMessage(value) {
  if (Array.isArray(value)) return value[0];
  return typeof value === 'string' ? value : undefined;
}

const INITIAL_FIELDS = {
  email: '',
  password: '',
  firstName: '',
  lastName: '',
  phoneNumber: '',
  birthDate: '', 
  heightCm: '',
  improvementGoals: '',
};

const INITIAL_CONSENTS = { privacy_notice: false, audio_storage: false, research: false };

// Owns RegisterScreen's state and submit flow.
export function useRegisterForm() {
  const { register } = useAuth();

  const [fields, setFields] = useState(INITIAL_FIELDS);
  const [consents, setConsents] = useState(INITIAL_CONSENTS);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function setField(name, value) {
    setFields((prev) => ({ ...prev, [name]: value }));
  }

  function toggleConsent(purpose, checked) {
    setConsents((prev) => ({ ...prev, [purpose]: checked }));
  }

  async function handleSubmit() {
    const errors = {
      email: validateEmail(fields.email),
      password: validatePassword(fields.password),
      firstName: fields.firstName.trim() ? null : 'Enter your first name.',
      lastName: fields.lastName.trim() ? null : 'Enter your last name.',
      phoneNumber: validatePhone(fields.phoneNumber),
      birthDate: validateBirthDate(fields.birthDate),
      heightCm: validateHeight(fields.heightCm),
      consents: consents.privacy_notice ? null : 'You must accept the privacy notice.',
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await register({
        ...fields,
        email: fields.email.trim(),
        birthDate: toIsoBirthDate(fields.birthDate),
        consents: Object.keys(consents).filter((purpose) => consents[purpose]),
      });
      router.replace('/');
    } catch (error) {
      if (__DEV__) logRequestError('Register', error);
      // Map the backend's field errors 
      // handling the duplicate-email case.
      const backendErrors = error.data && typeof error.data === 'object' ? error.data : null;
      const mapped = backendErrors && {
        email: firstMessage(backendErrors.email),
        password: firstMessage(backendErrors.password),
        firstName: firstMessage(backendErrors.first_name),
        lastName: firstMessage(backendErrors.last_name),
        phoneNumber: firstMessage(backendErrors.phone_number),
        birthDate: firstMessage(backendErrors.birth_date),
        heightCm: firstMessage(backendErrors.height_cm),
        consents: firstMessage(backendErrors.consents),
      };

      if (mapped && Object.values(mapped).some(Boolean)) {
        setFieldErrors((prev) => ({ ...prev, ...mapped }));
      } else {
        setFormError('Something went wrong. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return { fields, setField, consents, toggleConsent, fieldErrors, formError, submitting, handleSubmit };
}
