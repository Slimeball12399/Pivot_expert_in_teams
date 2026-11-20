import { Feather } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function ChecklistRow({ label, value }) {
  const { theme } = useTheme();
  return (
    <View style={[styles.checklistRow, { borderColor: theme.colors.border }]}>
      <View style={styles.checklistLabel}>
        <Feather name="check-circle" size={16} color={theme.colors.success} />
        <Text style={{ color: theme.colors.text }}>{label}</Text>
      </View>
      <Text style={{ color: theme.colors.textSecondary }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  checklistRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, borderBottomWidth: 1 },
  checklistLabel: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
