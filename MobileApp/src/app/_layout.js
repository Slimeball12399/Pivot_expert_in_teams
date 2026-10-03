import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { AppProviders } from '../providers/AppProviders';

// Root layout: replaces App.js. Providers wrap the navigator so every screen can use them.
export default function RootLayout() {
  return (
    <AppProviders>
      <Stack>
        <Stack.Screen name="index" options={{ title: 'Home' }} />
      </Stack>
      <StatusBar style="auto" />
    </AppProviders>
  );
}
