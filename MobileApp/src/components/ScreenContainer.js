import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../providers/ThemeProvider';

// Shared screen wrapper: safe-area + themed background + padding, every screen uses it
// instead of styling its own container. `scroll` wraps content in a ScrollView for forms
// (registration has many fields) and handles the keyboard pushing content up 


export function ScreenContainer({ children, scroll = false }) {
  const { theme } = useTheme();
  const Content = scroll ? ScrollView : View;

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.background }]}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <Content
          style={styles.flex}
          contentContainerStyle={scroll ? styles.content : undefined}
          keyboardShouldPersistTaps="handled"
        >
          {scroll ? children : <View style={styles.content}>{children}</View>}
        </Content>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  flex: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
    padding: 24,
    paddingBottom: 48,
  },
});
