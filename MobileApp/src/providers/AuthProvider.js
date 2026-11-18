import { createContext, useContext, useEffect, useState } from 'react';

import * as authApi from '../api/auth';
import { clearTokens, getTokens, saveTokens } from '../utils/storage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // On launch: if a token is already stored, fetch the user 
  useEffect(() => {
    (async () => {
      const { accessToken } = await getTokens();
      if (accessToken) {
        try {
          setUser(await authApi.me());
        } catch {
          await clearTokens();
        }
      }
      setIsLoading(false);
    })();
  }, []);

  async function login(email, password) {
    const tokens = await authApi.login({ email, password });
    await saveTokens(tokens);
    setUser(await authApi.me());
  }

  // The register endpoint only creates the account (no tokens back), so log
  // in with the same credentials right after to land the user inside the app.
  async function register(fields) {
    await authApi.register(fields);
    await login(fields.email, fields.password);
  }

  async function logout() {
    const { refreshToken } = await getTokens();
    if (refreshToken) {
      await authApi.logout(refreshToken).catch(() => {});
    }
    await clearTokens();
    setUser(null);
  }

  const value = { user, isLoading, isAuthenticated: !!user, login, register, logout };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
