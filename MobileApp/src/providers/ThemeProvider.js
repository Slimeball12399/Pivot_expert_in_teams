import { createContext, useContext, useState } from 'react';
import { useColorScheme } from 'react-native';
import { DefaultTheme, ThemeProvider as NavigationThemeProvider } from 'expo-router';

import { dark, light } from '../../assets/styles/colors';

const ThemeContext = createContext(null);
const palettes = { light, dark };

function buildTheme(colors) {
  return {
    colors,
    sizes: {
      icon: {
        small: 16,
        standard: 24,
        medium: 32,
      },
    },
    // Fonts match the web app's design system: Jost for headings, Outfit
    // for body (Server/web/templates/web/base.html).
    styles: {
      text: {
        title: {
          fontFamily: 'Jost_700Bold',
          fontSize: 24,
          color: colors.text,
        },
        body: {
          fontFamily: 'Outfit_400Regular',
          fontSize: 14,
          color: colors.text,
        },
      },
    },
  };
}

export function ThemeProvider({ children }) {
  const systemScheme = useColorScheme();
  // null = follow the device's system setting. 
  const [override, setOverride] = useState(null);

  const scheme = override ?? systemScheme ?? 'dark';
  const colors = palettes[scheme];
  const theme = buildTheme(colors);

  // Gives the navigator (headers, screen backgrounds) the same colors as the app.
  const navigationTheme = {
    ...DefaultTheme,
    colors: {
      ...DefaultTheme.colors,
      primary: colors.primary,
      background: colors.background,
      card: colors.surface,
      text: colors.text,
      border: colors.border,
    },
  };

  return (
    <ThemeContext.Provider value={{ theme, scheme, setScheme: setOverride }}>
      <NavigationThemeProvider value={navigationTheme}>{children}</NavigationThemeProvider>
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
