import Constants from 'expo-constants';

import { clearTokens, getTokens, saveTokens } from '../utils/storage';

// Django's runserver default. Change here if the backend runs on another port.
const BACKEND_PORT = 8000;

// Derives the backend host from the Metro dev server's own address
// (Constants.expoConfig.hostUri, e.g. "192.168.1.23:8081") instead of hardcoding
// 10.0.2.2 (Android emulator) or localhost (iOS simulator) — this one value works
function resolveBaseUrl() {
  const hostUri = Constants.expoConfig?.hostUri;
  const host = hostUri ? hostUri.split(':')[0] : 'localhost';
  return `http://${host}:${BACKEND_PORT}/api`;
}

export const API_BASE_URL = resolveBaseUrl();

class ApiError extends Error {
  constructor(status, data) {
    super(typeof data?.detail === 'string' ? data.detail : 'Request failed');
    this.status = status;
    this.data = data;
  }
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function rawRequest(path, { method = 'GET', body, accessToken } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await parseBody(response);
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

// Refreshes the access token using the stored refresh token.
// blacklists the refresh token sent in, so the new one returned must replace it.
async function refreshAccessToken() {
  const { refreshToken } = await getTokens();
  if (!refreshToken) return null;

  try {
    const data = await rawRequest('/auth/refresh/', { method: 'POST', body: { refresh: refreshToken } });
    await saveTokens({ access: data.access, refresh: data.refresh });
    return data.access;
  } catch {
    await clearTokens();
    return null;
  }
}

// Authenticated request: attaches the stored access token, and on a 401
// refreshes once and retries before giving up.
export async function apiRequest(path, options = {}) {
  const { accessToken } = await getTokens();

  try {
    return await rawRequest(path, { ...options, accessToken });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && accessToken) {
      const newAccessToken = await refreshAccessToken();
      if (newAccessToken) {
        return rawRequest(path, { ...options, accessToken: newAccessToken });
      }
    }
    throw error;
  }
}

// Public request: no stored token attached, no refresh-and-retry (login/register).
export function publicRequest(path, options = {}) {
  return rawRequest(path, options);
}

export { ApiError };
