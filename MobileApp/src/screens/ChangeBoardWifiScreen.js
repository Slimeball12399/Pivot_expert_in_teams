import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text } from 'react-native';

import { fetchWifiNetworks, updateBoardWifi } from '../api/boards';
import { LoadErrorState } from '../components/LoadErrorState';
import { ScreenContainer } from '../components/ScreenContainer';
import { ScreenHeader } from '../components/ScreenHeader';
import { WifiListSkeleton } from '../components/WifiListSkeleton';
import { WifiNetworkPicker } from '../components/WifiNetworkPicker';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

export function ChangeBoardWifiScreen({ boardId }) {
  const { theme } = useTheme();
  const [networks, setNetworks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [selectedSsid, setSelectedSsid] = useState(null);
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setNetworks(await fetchWifiNetworks());
      } catch {
        setLoadError('Could not load Wi-Fi networks. Check your connection and try again.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selectedNetwork = networks.find((network) => network.ssid === selectedSsid);
  const canSend = !!selectedNetwork && (password.length > 0 || selectedNetwork.security === 'Open');

  async function handleSave() {
    setSaving(true);
    try {
      await updateBoardWifi(boardId, selectedSsid);
      router.back();
    } catch {
      Alert.alert('Could not update Wi-Fi', 'Check your connection and try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScreenContainer scroll>
      <ScreenHeader kicker={boardId} title="Change Wi-Fi" onBack={() => router.back()} />

      {loadError ? (
        <LoadErrorState message={loadError} />
      ) : loading ? (
        <WifiListSkeleton />
      ) : (
        <>
          <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>
            Networks the board can see. Pick the one in the room where it will be used.
          </Text>
          <WifiNetworkPicker
            networks={networks}
            selectedSsid={selectedSsid}
            onSelect={setSelectedSsid}
            password={password}
            onChangePassword={setPassword}
          />
          <Button title="Send to board" onPress={handleSave} disabled={!canSend} loading={saving} />
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  helper: { fontSize: 13, marginTop: 20, marginBottom: 12, lineHeight: 18 },
});
