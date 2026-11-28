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

// The field shows DD/MM/YYYY.
function parseDateOnly(value) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value || '');
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return null;
  return date;
}

function ageOn(birthDate, today) {
  const hadBirthday =
    today.getMonth() > birthDate.getMonth() ||
    (today.getMonth() === birthDate.getMonth() && today.getDate() >= birthDate.getDate());
  return today.getFullYear() - birthDate.getFullYear() - (hadBirthday ? 0 : 1);
}

export function validateBirthDate(value) {
  const birthDate = parseDateOnly(value);
  if (!birthDate) return 'Enter your date of birth as DD/MM/YYYY.';
  const today = new Date();
  if (birthDate > today) return "Birth date can't be in the future.";
  if (ageOn(birthDate, today) < MIN_AGE) return `You must be at least ${MIN_AGE} years old.`;
  return null;
}

export function ageFromBirthDate(value) {
  const birthDate = parseDateOnly(value);
  return birthDate ? ageOn(birthDate, new Date()) : null;
}

// DD/MM/YYYY (what the field shows) -> YYYY-MM-DD (what the backend's
// DateField expects on the wire). null when `value` isn't a valid date;
export function toIsoBirthDate(value) {
  const date = parseDateOnly(value);
  if (!date) return null;
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function fromIsoBirthDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
}

export function validateHeight(heightCm) {
  const value = Number(heightCm);
  if (!Number.isFinite(value)) return 'Enter your height in cm.';
  if (value < MIN_HEIGHT_CM || value > MAX_HEIGHT_CM) {
    return `Height must be between ${MIN_HEIGHT_CM} and ${MAX_HEIGHT_CM} cm.`;
  }
  return null;
}

// Danish mobile numbers: the field only asks for the 8 digits.
export function normalizeDanishPhone(value) {
  const digits = (value || '').replace(/\D/g, '');
  const local =
    digits.length === 12 && digits.startsWith('0045') ? digits.slice(4)
      : digits.length === 10 && digits.startsWith('45') ? digits.slice(2)
        : digits;
  return /^\d{8}$/.test(local) ? `+45${local}` : null;
}

export function validatePhone(value) {
  return normalizeDanishPhone(value) ? null : 'Enter the 8-digit phone number.';
}
