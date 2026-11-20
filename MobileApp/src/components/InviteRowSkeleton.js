import { StyleSheet, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { Skeleton } from './Skeleton';

export function InviteRowSkeleton() {
  const { theme } = useTheme();
  return (
    <View style={[styles.card, styles.row, { backgroundColor: theme.colors.surface }]}>
      <View>
        <Skeleton width={140} height={18} style={styles.skeletonGap} />
        <Skeleton width={110} height={13} />
      </View>
      <Skeleton width={20} height={20} borderRadius={10} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 20, padding: 20, marginTop: 20 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  skeletonGap: { marginBottom: 6 },
});
