import { useState } from 'react';

import { updateMe } from '../api/auth';
import { logRequestError } from '../api/client';
import { useAuth } from '../providers/AuthProvider';
import {
  fromIsoBirthDate,
  normalizeDanishPhone,
  toIsoBirthDate,
  validateBirthDate,
  validateHeight,
  validatePhone,
} from '../utils/validators';

function firstMessage(value) {
  if (Array.isArray(value)) return value[0];
  return typeof value === 'string' ? value : undefined;
}

function localPhone(phoneNumber) {
  return (phoneNumber || '').replace(/^\+?45/, '');
}

const EMPTY_FIELDS = { firstName: '', lastName: '', phoneNumber: '', birthDate: '', heightCm: '', improvementGoals: '' };

function fieldsFromUser(user) {
  if (!user) return EMPTY_FIELDS;
  return {
    firstName: user.first_name,
    lastName: user.last_name,
    phoneNumber: localPhone(user.phone_number),
    birthDate: fromIsoBirthDate(user.profile?.birth_date),
    heightCm: user.profile?.height_cm ? String(user.profile.height_cm) : '',
    improvementGoals: user.profile?.improvement_goals ?? '',
  };
}

// Owns ProfileScreen's view/edit state and the PATCH /api/me/ submit flow.
export function useProfileForm() {
  const { user, updateUser } = useAuth();
  const isSpeaker = user?.role === 'speaker';

  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState(() => fieldsFromUser(user));
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function setField(name, value) {
    setFields((prev) => ({ ...prev, [name]: value }));
  }

  function startEditing() {
    setFields(fieldsFromUser(user));
    setFieldErrors({});
    setFormError(null);
    setSuccessMessage(null);
    setEditing(true);
  }

  function cancelEditing() {
    setFieldErrors({});
    setFormError(null);
    setEditing(false);
  }

  async function handleSave() {
    const errors = {
      firstName: fields.firstName.trim() ? null : 'Enter your first name.',
      lastName: fields.lastName.trim() ? null : 'Enter your last name.',
      phoneNumber: validatePhone(fields.phoneNumber),
      ...(isSpeaker && {
        birthDate: validateBirthDate(fields.birthDate),
        heightCm: validateHeight(fields.heightCm),
      }),
    };
    setFieldErrors(errors);
    if (Object.values(errors).some(Boolean)) return;

    setFormError(null);
    setSubmitting(true);
    try {
      const payload = {
        first_name: fields.firstName.trim(),
        last_name: fields.lastName.trim(),
        phone_number: normalizeDanishPhone(fields.phoneNumber),
      };
      if (isSpeaker) {
        payload.profile = {
          birth_date: toIsoBirthDate(fields.birthDate),
          height_cm: Number(fields.heightCm),
          improvement_goals: fields.improvementGoals,
        };
      }
      const updated = await updateMe(payload);
      updateUser(updated);
      setEditing(false);
      setSuccessMessage('Profile updated.');
    } catch (error) {
      if (__DEV__) logRequestError('Update profile', error);
      const backendErrors = error.data && typeof error.data === 'object' ? error.data : null;
      const profileErrors = backendErrors?.profile || {};
      const mapped = backendErrors && {
        firstName: firstMessage(backendErrors.first_name),
        lastName: firstMessage(backendErrors.last_name),
        phoneNumber: firstMessage(backendErrors.phone_number),
        birthDate: firstMessage(profileErrors.birth_date),
        heightCm: firstMessage(profileErrors.height_cm),
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

  return {
    user,
    isSpeaker,
    editing,
    fields,
    setField,
    fieldErrors,
    formError,
    successMessage,
    submitting,
    startEditing,
    cancelEditing,
    handleSave,
  };
}
