import { useEffect, useState } from 'react';
import { Animated, StyleSheet } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// A pulsing placeholder block, for skeleton loading states.
export function Skeleton({ width, height, borderRadius = 8, style }) {
  const { theme } = useTheme();
  const [opacity] = useState(() => new Animated.Value(0.4));

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 650, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 650, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        styles.base,
        { width, height, borderRadius, backgroundColor: theme.colors.border, opacity },
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  base: { overflow: 'hidden' },
});
