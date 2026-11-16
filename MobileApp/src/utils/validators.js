export const MIN_AGE = 16;
export const MIN_HEIGHT_CM = 100;
export const MAX_HEIGHT_CM = 250;
export const MIN_PASSWORD_LENGTH = 8;

export function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ? null : 'Enter a valid email address.';
}

export function validatePassword(password) {
  if (!password || password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return null;
}

function ageOn(birthDate, today) {
  const hadBirthday =
    today.getMonth() > birthDate.getMonth() ||
    (today.getMonth() === birthDate.getMonth() && today.getDate() >= birthDate.getDate());
  return today.getFullYear() - birthDate.getFullYear() - (hadBirthday ? 0 : 1);
}

export function validateBirthDate(birthDate) {
  if (!birthDate) return 'Enter your date of birth.';
  const today = new Date();
  if (birthDate > today) return "Birth date can't be in the future.";
  if (ageOn(birthDate, today) < MIN_AGE) return `You must be at least ${MIN_AGE} years old.`;
  return null;
}

export function validateHeight(heightCm) {
  const value = Number(heightCm);
  if (!Number.isFinite(value)) return 'Enter your height in cm.';
  if (value < MIN_HEIGHT_CM || value > MAX_HEIGHT_CM) {
    return `Height must be between ${MIN_HEIGHT_CM} and ${MAX_HEIGHT_CM} cm.`;
  }
  return null;
}

// Danish mobile numbers: 8 digits, with or without a +45/0045 prefix.
// Normalized to the form the backend's PhoneNumberField (region="DK").
export function normalizeDanishPhone(value) {
  const digits = (value || '').replace(/\D/g, '');
  const local = digits.startsWith('45') && digits.length === 10 ? digits.slice(2) : digits;
  return /^\d{8}$/.test(local) ? `+45${local}` : null;
}

export function validatePhone(value) {
  return normalizeDanishPhone(value) ? null : 'Enter a valid Danish phone number (8 digits).';
}
