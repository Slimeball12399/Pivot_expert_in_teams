import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function Checkbox({ checked, onToggle, label }) {
  const { theme } = useTheme();
  const { colors } = theme;

  return (
    <Pressable style={styles.row} onPress={() => onToggle(!checked)}>
      <View
        style={[
          styles.box,
          { borderColor: colors.border },
          checked && { backgroundColor: colors.primary, borderColor: colors.primary },
        ]}
      >
        {checked && <Text style={{ color: colors.primaryText, fontSize: 13, fontWeight: '700' }}>✓</Text>}
      </View>
      <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  box: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  label: {
    flex: 1,
    fontSize: 14,
  },
});
