import { Feather } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

// A back chevron beside a kicker + title on one row 
export function ScreenHeader({ kicker, title, onBack }) {
  const { theme } = useTheme();
  return (
    <View style={styles.row}>
      {onBack && (
        <Pressable onPress={onBack} hitSlop={12} style={styles.back}>
          <Feather name="chevron-left" size={24} color={theme.colors.text} />
        </Pressable>
      )}
      <View style={styles.text}>
        {kicker && <Text style={[styles.kicker, { color: theme.colors.textSecondary }]}>{kicker}</Text>}
        <Text style={theme.styles.text.title}>{title}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 20 },
  back: { marginRight: 10, marginTop: 2 },
  text: { flex: 1 },
  kicker: { fontSize: 13, marginBottom: 4 },
});
