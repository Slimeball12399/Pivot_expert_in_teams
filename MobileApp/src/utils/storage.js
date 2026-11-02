import * as SecureStore from 'expo-secure-store';

const ACCESS_TOKEN_KEY = 'pivot_access_token';
const REFRESH_TOKEN_KEY = 'pivot_refresh_token';

export async function getTokens() {
  const [accessToken, refreshToken] = await Promise.all([
    SecureStore.getItemAsync(ACCESS_TOKEN_KEY),
    SecureStore.getItemAsync(REFRESH_TOKEN_KEY),
  ]);
  return { accessToken, refreshToken };
}

export async function saveTokens({ access, refresh }) {
  await Promise.all([
    SecureStore.setItemAsync(ACCESS_TOKEN_KEY, access),
    refresh ? SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refresh) : Promise.resolve(),
  ]);
}

export async function clearTokens() {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY),
    SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY),
  ]);
}
