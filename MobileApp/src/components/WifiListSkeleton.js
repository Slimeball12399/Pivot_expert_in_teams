import { StyleSheet, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { Skeleton } from './Skeleton';

// Mimics WifiNetworkPicker's row shape while the network scan is in flight.
export function WifiListSkeleton({ rows = 4 }) {
  const { theme } = useTheme();
  return (
    <View style={[styles.list, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
      {Array.from({ length: rows }).map((_, index) => (
        <View
          key={index}
          style={[styles.row, index > 0 && { borderTopWidth: 1, borderTopColor: theme.colors.border }]}
        >
          <Skeleton width={20} height={20} borderRadius={10} />
          <View style={styles.text}>
            <Skeleton width={120} height={15} style={styles.gap} />
            <Skeleton width={90} height={12} />
          </View>
          <Skeleton width={18} height={18} borderRadius={4} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { borderWidth: 1, borderRadius: 14, marginBottom: 16, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 },
  text: { flex: 1 },
  gap: { marginBottom: 6 },
});
