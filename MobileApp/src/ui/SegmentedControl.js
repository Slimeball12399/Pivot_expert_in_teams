import { useEffect, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

const PADDING = 4;

export function SegmentedControl({ options, value, onChange }) {
  const { theme } = useTheme();
  const { colors } = theme;

  const [trackWidth, setTrackWidth] = useState(0);
  const activeIndex = options.findIndex((option) => option.value === value);
  // Lazy useState initializer
  const [slide] = useState(() => new Animated.Value(activeIndex));

  useEffect(() => {
    Animated.spring(slide, {
      toValue: activeIndex,
      useNativeDriver: true,
      speed: 20,
      bounciness: 6,
    }).start();
  }, [activeIndex, slide]);

  const segmentWidth = trackWidth > 0 ? (trackWidth - PADDING * 2) / options.length : 0;
  const translateX = slide.interpolate({
    inputRange: options.map((_, i) => i),
    outputRange: options.map((_, i) => i * segmentWidth),
  });

  return (
    <View
      style={[styles.track, { backgroundColor: colors.surface, borderColor: colors.border }]}
      onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
    >
      {trackWidth > 0 && (
        <Animated.View
          style={[styles.thumb, { backgroundColor: colors.primary, width: segmentWidth, transform: [{ translateX }] }]}
        />
      )}
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable key={option.value} onPress={() => onChange(option.value)} style={styles.option}>
            <Text style={[styles.label, { color: active ? colors.primaryText : colors.text }]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: 'row',
    borderWidth: 1,
    borderRadius: 14,
    padding: PADDING,
    marginBottom: 24,
  },
  thumb: {
    position: 'absolute',
    top: PADDING,
    bottom: PADDING,
    left: PADDING,
    borderRadius: 10,
  },
  option: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  label: {
    fontSize: 15,
    fontWeight: '700',
  },
});
