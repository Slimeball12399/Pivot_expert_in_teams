import { Jost_700Bold } from '@expo-google-fonts/jost';
import { Outfit_400Regular } from '@expo-google-fonts/outfit';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { AppProviders } from '../providers/AppProviders';

// Root layout: replaces App.js. Providers wrap the navigator so every screen can use them.
// Fonts match the web app's design system (Jost for headings, Outfit for
// body) — nothing renders until they're ready, so there's no font-swap flash.
export default function RootLayout() {
  const [fontsLoaded] = useFonts({ Jost_700Bold, Outfit_400Regular });

  if (!fontsLoaded) return null;

  return (
    <AppProviders>
      <Stack>
        <Stack.Screen name="index" options={{ title: 'Home' }} />
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="auto" />
    </AppProviders>
  );
}
