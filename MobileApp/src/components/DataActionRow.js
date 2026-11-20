import { Feather } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { onDanger } from '../../assets/styles/colors';

export function DataActionRow({ icon, title, subtitle, onPress, danger }) {
  const { theme } = useTheme();
  const textColor = danger ? onDanger : theme.colors.text;
  const subtitleColor = danger ? 'rgba(255,255,255,0.85)' : theme.colors.textSecondary;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.dataRow,
        danger ? { backgroundColor: theme.colors.danger } : { borderWidth: 1, borderColor: theme.colors.border },
        pressed && { opacity: 0.85 },
      ]}
    >
      <Feather name={icon} size={20} color={textColor} />
      <View style={styles.dataRowText}>
        <Text style={[styles.dataRowTitle, { color: textColor }]}>{title}</Text>
        <Text style={[styles.dataRowSubtitle, { color: subtitleColor }]}>{subtitle}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dataRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    borderRadius: 14,
    padding: 14,
    marginTop: 10,
  },
  dataRowText: {
    flex: 1,
  },
  dataRowTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  dataRowSubtitle: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
});
