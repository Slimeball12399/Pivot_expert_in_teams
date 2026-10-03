import { createContext, useContext } from 'react';

const EmptyContext = createContext(null);

// Placeholder provider — rename it and add shared state here when you need it.
export function EmptyProvider({ children }) {
  const value = {};

  return <EmptyContext.Provider value={value}>{children}</EmptyContext.Provider>;
}

export const useEmpty = () => useContext(EmptyContext);
