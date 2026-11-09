import { apiRequest, publicRequest } from './client';
import { normalizeDanishPhone } from '../utils/validators';

// POST /api/auth/login/ .. JWT
export function login({ email, password }) {
  return publicRequest('/auth/login/', { method: 'POST', body: { email, password } });
}

// POST /api/auth/register/ 
export function register({
  email,
  password,
  firstName,
  lastName,
  phoneNumber,
  birthDate,
  heightCm,
  consents,
  improvementGoals = '',
}) {
  return publicRequest('/auth/register/', {
    method: 'POST',
    body: {
      email,
      password,
      first_name: firstName,
      last_name: lastName,
      phone_number: normalizeDanishPhone(phoneNumber),
      birth_date: birthDate, // "YYYY-MM-DD"
      height_cm: Number(heightCm),
      consents,
      improvement_goals: improvementGoals,
    },
  });
}

// POST /api/auth/verify-email/ — request a new code (register/login already
// trigger the first one on the backend; this is the "resend" button).
export function resendVerificationCode(email) {
  return publicRequest('/auth/verify-email/', { method: 'POST', body: { email } });
}

// PUT /api/auth/verify-email/ — confirm the code. 
export function verifyEmail(email, code) {
  return publicRequest('/auth/verify-email/', { method: 'PUT', body: { email, code } });
}

// POST /api/auth/refresh/
export function refresh(refreshToken) {
  return publicRequest('/auth/refresh/', { method: 'POST', body: { refresh: refreshToken } });
}

// POST /api/auth/logout/ 
export function logout(refreshToken) {
  return apiRequest('/auth/logout/', { method: 'POST', body: { refresh: refreshToken } });
}

// GET /api/me/ — the logged-in user plus their role-specific profile.
export function me() {
  return apiRequest('/me/');
}
