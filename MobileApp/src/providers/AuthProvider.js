import { createContext, useContext } from 'react';

const AuthContext = createContext(null);

// (user, isLoading, isAuthenticated) and login()/register()/logout() etc..

export function AuthProvider({ children }) {
  const value = {};

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
