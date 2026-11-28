import { createContext, useContext, useEffect, useState } from 'react';

import * as authApi from '../api/auth';
import { clearTokens, getTokens, saveTokens } from '../utils/storage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingVerification, setPendingVerification] = useState(null);

  const [passwordReset, setPasswordReset] = useState(null);

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

  async function register(fields) {
    await authApi.register(fields);
  }


  function needsVerification(email, password) {
    setPendingVerification({ email, password });
  }

  function clearVerification() {
    setPendingVerification(null);
  }

  function startPasswordReset(email) {
    setPasswordReset({ email });
  }

  // Called once the reset code's confirmed, to carry the uid/token into the
  // new-password screen.
  function setPasswordResetToken(uid, resetToken) {
    setPasswordReset((prev) => prev && { ...prev, uid, resetToken });
  }

  function clearPasswordReset() {
    setPasswordReset(null);
  }

  // Called after PATCH /api/me/ succeeds, with the response's fresh user data.
  function updateUser(nextUser) {
    setUser(nextUser);
  }

  async function logout() {
    const { refreshToken } = await getTokens();
    if (refreshToken) {
      await authApi.logout(refreshToken).catch(() => {});
    }
    await clearTokens();
    setUser(null);
  }

  const value = {
    user, isLoading, isAuthenticated: !!user, login, register, logout, updateUser,
    pendingVerification, needsVerification, clearVerification,
    passwordReset, startPasswordReset, setPasswordResetToken, clearPasswordReset,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
