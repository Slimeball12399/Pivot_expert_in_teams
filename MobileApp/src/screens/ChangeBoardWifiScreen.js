import { router } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { LoadErrorState } from '../components/LoadErrorState';
import { ScreenContainer } from '../components/ScreenContainer';
import { ScreenHeader } from '../components/ScreenHeader';
import { WifiListSkeleton } from '../components/WifiListSkeleton';
import { WifiNetworkPicker } from '../components/WifiNetworkPicker';
import { useChangeBoardWifi } from '../hooks/useChangeBoardWifi';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

export function ChangeBoardWifiScreen({ boardId }) {
  const { theme } = useTheme();
  const {
    networks,
    loading,
    loadError,
    selectedSsid,
    setSelectedSsid,
    password,
    setPassword,
    saving,
    canSend,
    handleSave,
  } = useChangeBoardWifi(boardId);

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
