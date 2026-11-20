import { StyleSheet, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { Skeleton } from './Skeleton';

export function BoardRowSkeleton() {
  const { theme } = useTheme();
  return (
    <View style={[styles.row, { backgroundColor: theme.colors.surface }]}>
      <Skeleton width={44} height={44} borderRadius={12} />
      <View style={styles.rowText}>
        <Skeleton width={160} height={16} style={styles.skeletonGapLarge} />
        <Skeleton width={90} height={13} style={styles.skeletonGap} />
        <Skeleton width={120} height={12} />
      </View>
      <Skeleton width={20} height={20} borderRadius={10} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
  },
  rowText: {
    flex: 1,
  },
  skeletonGapLarge: {
    marginBottom: 8,
  },
  skeletonGap: {
    marginBottom: 6,
  },
});
