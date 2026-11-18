import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// The seesaw icon + "pivot" wordmark .
export function BrandMark({ badge, subtitle }) {
  const { theme } = useTheme();
  const { colors } = theme;

  return (
    <View style={styles.wrapper}>
      <View style={styles.icon}>
        <View style={[styles.fulcrum, { borderBottomColor: colors.text }]} />
        <View style={[styles.beam, { backgroundColor: colors.text }]} />
        <View style={[styles.ball, { backgroundColor: colors.accent }]} />
      </View>

      <View style={styles.wordmarkRow}>
        <Text style={[styles.wordmark, { color: colors.text }]}>pivot</Text>
        {badge && (
          <View style={[styles.badge, { backgroundColor: colors.primary }]}>
            <Text style={[styles.badgeText, { color: colors.primaryText }]}>{badge}</Text>
          </View>
        )}
      </View>

      {subtitle && <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{subtitle}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { alignItems: 'center', marginBottom: 24 },
  icon: { width: 110, height: 60, marginBottom: 8 },
  fulcrum: {
    position: 'absolute',
    bottom: 4,
    left: 42,
    width: 0,
    height: 0,
    borderLeftWidth: 13,
    borderRightWidth: 13,
    borderBottomWidth: 22,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
  },
  beam: {
    position: 'absolute',
    top: 26,
    left: 5,
    width: 100,
    height: 7,
    borderRadius: 4,
    transform: [{ rotate: '-16deg' }],
  },
  ball: {
    position: 'absolute',
    top: 2,
    right: 2,
    width: 26,
    height: 26,
    borderRadius: 13,
  },
  wordmarkRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  wordmark: { fontFamily: 'Jost_400Regular', fontSize: 40 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  subtitle: {
    fontFamily: 'Outfit_400Regular',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 12,
    paddingHorizontal: 16,
  },
});
