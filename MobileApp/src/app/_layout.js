import { Jost_400Regular, Jost_700Bold } from '@expo-google-fonts/jost';
import { Outfit_400Regular } from '@expo-google-fonts/outfit';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { AppProviders } from '../providers/AppProviders';


// A spinner here
export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({ Jost_400Regular, Jost_700Bold, Outfit_400Regular });

  if (fontError) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Failed to load fonts: {fontError.message}</Text>
      </View>
    );
  }

  if (!fontsLoaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <AppProviders>
      <Stack>
        <Stack.Screen name="index" options={{ title: 'Home' }} />
        <Stack.Screen name="profile" options={{ title: 'Profile' }} />
        <Stack.Screen name="change-password" options={{ title: 'Change password' }} />
        <Stack.Screen name="user/[id]" options={{ title: 'User profile' }} />
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="auto" />
    </AppProviders>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  errorText: { textAlign: 'center' },
});
