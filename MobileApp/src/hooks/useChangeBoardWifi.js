import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert } from 'react-native';

import { fetchWifiNetworks, updateBoardWifi } from '../api/boards';

// Owns ChangeBoardWifiScreen's network list + the send-to-board submit flow.
export function useChangeBoardWifi(boardId) {
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

  return {
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
  };
}
