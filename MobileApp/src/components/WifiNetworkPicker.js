import { Feather } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';
import { TextInput } from '../ui/TextInput';

export function WifiNetworkPicker({ networks, selectedSsid, onSelect, password, onChangePassword }) {
  const { theme } = useTheme();
  const selected = networks.find((network) => network.ssid === selectedSsid);

  return (
    <View>
      <View style={[styles.list, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
        {networks.map((network, index) => (
          <Pressable
            key={network.ssid}
            disabled={network.disabled}
            onPress={() => onSelect(network.ssid)}
            style={[
              styles.row,
              index > 0 && { borderTopWidth: 1, borderTopColor: theme.colors.border },
              network.ssid === selectedSsid && { backgroundColor: theme.colors.primary + '1A' },
              network.disabled && { opacity: 0.5 },
            ]}
          >
            <View
              style={[
                styles.radio,
                { borderColor: network.ssid === selectedSsid ? theme.colors.primary : theme.colors.border },
              ]}
            >
              {network.ssid === selectedSsid && (
                <View style={[styles.radioDot, { backgroundColor: theme.colors.primary }]} />
              )}
            </View>
            <View style={styles.rowText}>
              <Text style={[styles.ssid, { color: theme.colors.text }]}>{network.ssid}</Text>
              <Text style={[styles.meta, { color: theme.colors.textSecondary }]}>
                {network.security}{!network.disabled && ` · ${network.signal}`}
              </Text>
            </View>
            <Feather name="wifi" size={18} color={theme.colors.textSecondary} />
          </Pressable>
        ))}
      </View>

      {selected && !selected.disabled && (
        <TextInput
          label={`Password for ${selected.ssid}`}
          value={password}
          onChangeText={onChangePassword}
          secureTextEntry
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    borderWidth: 1,
    borderRadius: 14,
    marginBottom: 16,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
  },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  rowText: {
    flex: 1,
  },
  ssid: {
    fontSize: 15,
    fontWeight: '700',
  },
  meta: {
    fontSize: 12,
    marginTop: 2,
  },
});
