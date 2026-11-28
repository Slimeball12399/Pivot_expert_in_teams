import { Feather } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

const SIZE = 96;
const DOT_SIZE = 12;


const ROTATION = { front: '0deg', right: '90deg', back: '180deg', left: '270deg' };
const POSITION = {
  front: { top: -DOT_SIZE / 2, left: SIZE / 2 - DOT_SIZE / 2 },
  back: { bottom: -DOT_SIZE / 2, left: SIZE / 2 - DOT_SIZE / 2 },
  left: { left: -DOT_SIZE / 2, top: SIZE / 2 - DOT_SIZE / 2 },
  right: { right: -DOT_SIZE / 2, top: SIZE / 2 - DOT_SIZE / 2 },
};

export function CalibrationCompass({ measurements, currentDirection, pulsing }) {
  const { theme } = useTheme();
  const [pulse] = useState(() => new Animated.Value(1));

  useEffect(() => {
    if (!pulsing) {
      pulse.setValue(1);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1.4, duration: 550, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 550, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulsing, pulse]);

  return (
    <View style={[styles.circle, { borderColor: theme.colors.border }]}>
      <View style={[styles.innerRing, { borderColor: theme.colors.border }]} />
      {currentDirection && (
        <View style={[styles.arrowWrap, { transform: [{ rotate: ROTATION[currentDirection] }] }]}>
          <Feather name="arrow-up" size={26} color={theme.colors.primary} />
        </View>
      )}
      {Object.keys(POSITION).map((direction) => (
        <Animated.View
          key={direction}
          style={[
            styles.dot,
            POSITION[direction],
            {
              backgroundColor: measurements[direction] != null
                ? theme.colors.success
                : direction === currentDirection
                  ? theme.colors.primary
                  : theme.colors.border,
              transform: [{ scale: direction === currentDirection ? pulse : 1 }],
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  circle: {
    width: SIZE,
    height: SIZE,
    borderRadius: SIZE / 2,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  innerRing: {
    position: 'absolute',
    width: SIZE * 0.6,
    height: SIZE * 0.6,
    borderRadius: (SIZE * 0.6) / 2,
    borderWidth: 1,
  },
  arrowWrap: {
    position: 'absolute',
  },
  dot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: DOT_SIZE / 2,
    position: 'absolute',
  },
});
