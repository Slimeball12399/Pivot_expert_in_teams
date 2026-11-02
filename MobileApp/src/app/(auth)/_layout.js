import { Stack } from 'expo-router';

// Shared stack for the pre-login flow. privacy-notice opens as a modal over
// register instead of a full push, since it's reference material, not a step.
export default function AuthLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login" />
      <Stack.Screen name="register" />
      <Stack.Screen name="privacy-notice" options={{ presentation: 'modal', headerShown: true, title: 'Privacy Notice' }} />
    </Stack>
  );
}
