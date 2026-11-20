import { StyleSheet, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function ProgressBar({ progress, style }) {
  const { theme } = useTheme();
  return (
    <View style={[styles.track, { backgroundColor: theme.colors.border }, style]}>
      <View style={[styles.fill, { backgroundColor: theme.colors.primary, width: `${progress * 100}%` }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
});
