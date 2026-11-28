import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert } from 'react-native';

import {
  addBoard, checkBoardHealth, fetchWifiNetworks, scanForBoards, sendWifiToBoard,
} from '../api/boards';

//Bluetooth scan, Wi-Fi hand-off, health check + save.
export function useAddBoard() {
  const [step, setStep] = useState(1);

  // Step 1: Bluetooth scan
  const [scanning, setScanning] = useState(true);
  const [scanResult, setScanResult] = useState(null);

  // Step 2: Wi-Fi
  const [networks, setNetworks] = useState([]);
  const [loadingNetworks, setLoadingNetworks] = useState(true);
  const [manualEntry, setManualEntry] = useState(false);
  const [manualSsid, setManualSsid] = useState('');
  const [selectedSsid, setSelectedSsid] = useState(null);
  const [password, setPassword] = useState('');
  const [sending, setSending] = useState(false);

  // Step 3: Check + name
  const [checking, setChecking] = useState(true);
  const [health, setHealth] = useState(null);
  const [location, setLocation] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const result = await scanForBoards();
        setScanResult(result);
      } catch {
        Alert.alert('Could not scan for boards', 'Check your connection and try again.');
      } finally {
        setScanning(false);
      }
    })();
  }, []);

  function goToWifiStep() {
    setStep(2);
    setLoadingNetworks(true);
    (async () => {
      try {
        setNetworks(await fetchWifiNetworks());
      } catch {
        Alert.alert('Could not load Wi-Fi networks', 'Check your connection and try again.');
      } finally {
        setLoadingNetworks(false);
      }
    })();
  }

  async function handleSendToBoard() {
    const ssid = manualEntry ? manualSsid.trim() : selectedSsid;
    if (!ssid) return;
    setSending(true);
    try {
      await sendWifiToBoard(scanResult.newBoard.id, ssid);
      setStep(3);
      setChecking(true);
      try {
        setHealth(await checkBoardHealth(scanResult.newBoard.id, ssid));
      } finally {
        setChecking(false);
      }
    } catch {
      Alert.alert('Could not send Wi-Fi to the board', 'Check your connection and try again.');
    } finally {
      setSending(false);
    }
  }

  async function handleSkip() {
    setSaving(true);
    try {
      await addBoard(scanResult.newBoard.id, location.trim() || scanResult.newBoard.id);
      router.replace('/(admin)/boards');
    } catch {
      Alert.alert('Could not save this board', 'Check your connection and try again.');
    } finally {
      setSaving(false);
    }
  }

  async function handleCalibrate() {
    setSaving(true);
    try {
      const savedLocation = location.trim() || scanResult.newBoard.id;
      await addBoard(scanResult.newBoard.id, savedLocation);
      router.replace(
        `/(admin)/boards/${scanResult.newBoard.id}/calibrate?location=${encodeURIComponent(savedLocation)}`,
      );
    } catch {
      Alert.alert('Could not save this board', 'Check your connection and try again.');
    } finally {
      setSaving(false);
    }
  }

  const selectedNetwork = networks.find((network) => network.ssid === selectedSsid);
  const canSend = manualEntry
    ? manualSsid.trim().length > 0
    : !!selectedNetwork && (password.length > 0 || selectedNetwork.security === 'Open');

  return {
    step,
    setStep,
    scanning,
    scanResult,
    networks,
    loadingNetworks,
    manualEntry,
    setManualEntry,
    manualSsid,
    setManualSsid,
    selectedSsid,
    setSelectedSsid,
    password,
    setPassword,
    sending,
    canSend,
    checking,
    health,
    location,
    setLocation,
    saving,
    goToWifiStep,
    handleSendToBoard,
    handleSkip,
    handleCalibrate,
  };
}
