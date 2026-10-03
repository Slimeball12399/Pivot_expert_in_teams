import { createContext, useContext } from 'react';
import { DefaultTheme, ThemeProvider as NavigationThemeProvider } from 'expo-router';

import { colors } from '../../assets/styles/colors';

const ThemeContext = createContext(null);

// App-wide theme: colors, sizes and shared styles.
const theme = {
  colors,
  sizes: {
    icon: {
      small: 16,
      standard: 24,
      medium: 32,
    },
  },
  styles: {
    text: {
      title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: colors.text,
      },
      body: {
        fontSize: 14,
        color: colors.text,
      },
    },
  },
};

// Gives the navigator (headers, screen backgrounds) the same colors as the app.
const navigationTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.primary,
    background: colors.background,
    card: colors.card,
    text: colors.text,
    border: colors.border,
  },
};

export function ThemeProvider({ children }) {
  return (
    <ThemeContext.Provider value={{ theme }}>
      <NavigationThemeProvider value={navigationTheme}>{children}</NavigationThemeProvider>
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
