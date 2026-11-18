import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import {
  addBoard, checkBoardHealth, fetchWifiNetworks, scanForBoards, sendWifiToBoard,
} from '../api/boards';
import { ScreenContainer } from '../components/ScreenContainer';
import { ScreenHeader } from '../components/ScreenHeader';
import { WifiListSkeleton } from '../components/WifiListSkeleton';
import { WifiNetworkPicker } from '../components/WifiNetworkPicker';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';

export function AddBoardScreen() {
  const { theme } = useTheme();
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
  const canSend = manualEntry ? manualSsid.trim().length > 0 : !!selectedNetwork && (password.length > 0 || selectedNetwork.security === 'Open');

  return (
    <ScreenContainer scroll>
      {step === 1 && (
        <>
          <ScreenHeader kicker="Step 1 of 3 · Bluetooth" title="Find the board" onBack={() => router.back()} />

          <View style={[styles.scanCard, { backgroundColor: theme.colors.surface }]}>
            <View style={[styles.bluetoothIcon, { backgroundColor: theme.colors.primary + '33' }]}>
              <Feather name="bluetooth" size={28} color={theme.colors.primary} />
            </View>
            <Text style={[styles.scanTitle, { color: theme.colors.text }]}>
              {scanning ? 'Looking for boards nearby' : 'Scan complete'}
            </Text>
            <Text style={[styles.scanHelper, { color: theme.colors.textSecondary }]}>
              Switch the board on and hold its button for 3 seconds until the light blinks blue.
            </Text>
            {scanning && <ActivityIndicator color={theme.colors.primary} style={styles.scanSpinner} />}
          </View>

          {!scanning && scanResult && (
            <>
              <Text style={[styles.foundLabel, { color: theme.colors.textSecondary }]}>
                FOUND {scanResult.alreadyPaired ? 2 : 1} BOARD{scanResult.alreadyPaired ? 'S' : ''}
              </Text>
              <View
                style={[
                  styles.boardRow,
                  styles.boardRowHighlight,
                  { backgroundColor: theme.colors.surface, borderColor: theme.colors.primary },
                ]}
              >
                <View style={styles.boardRowText}>
                  <Text style={[styles.boardRowTitle, { color: theme.colors.text }]}>{scanResult.newBoard.id}</Text>
                  <Text style={[styles.boardRowMeta, { color: theme.colors.textSecondary }]}>
                    New board · {scanResult.newBoard.signal} signal
                  </Text>
                </View>
                <Button title="Connect" onPress={goToWifiStep} style={styles.connectButton} />
              </View>
              {scanResult.alreadyPaired && (
                <View style={[styles.boardRow, { backgroundColor: theme.colors.surface }]}>
                  <View style={styles.boardRowText}>
                    <Text style={[styles.boardRowTitle, { color: theme.colors.text }]}>
                      {scanResult.alreadyPaired.id}
                    </Text>
                    <Text style={[styles.boardRowMeta, { color: theme.colors.textSecondary }]}>
                      Already on your account · {scanResult.alreadyPaired.location}
                    </Text>
                  </View>
                  <Button
                    title="Change Wi-Fi"
                    variant="outline"
                    onPress={() => router.replace(`/(admin)/boards/${scanResult.alreadyPaired.id}/wifi`)}
                    style={styles.connectButton}
                  />
                </View>
              )}
            </>
          )}

          <Text style={[styles.footerHelper, { color: theme.colors.textSecondary }]}>
            Keep your phone within a few metres of the board. Bluetooth must be on.
          </Text>
        </>
      )}

      {step === 2 && (
        <>
          <ScreenHeader
            kicker="Step 2 of 3 · Wi-Fi"
            title={`Connect ${scanResult.newBoard.id} to Wi-Fi`}
            onBack={() => setStep(1)}
          />
          <View style={[styles.connectedPill, { backgroundColor: theme.colors.success + '26' }]}>
            <View style={[styles.connectedDot, { backgroundColor: theme.colors.success }]} />
            <Text style={[styles.connectedText, { color: theme.colors.success }]}>Connected over Bluetooth</Text>
          </View>

          {loadingNetworks ? (
            <WifiListSkeleton />
          ) : manualEntry ? (
            <TextInput
              label="Network name"
              value={manualSsid}
              onChangeText={setManualSsid}
              placeholder="e.g. Studio-WiFi"
            />
          ) : (
            <>
              <Text style={[styles.scanHelper, { color: theme.colors.textSecondary, marginBottom: 12 }]}>
                Networks the board can see. Pick the one in the room where it will be used.
              </Text>
              <WifiNetworkPicker
                networks={networks}
                selectedSsid={selectedSsid}
                onSelect={setSelectedSsid}
                password={password}
                onChangePassword={setPassword}
              />
            </>
          )}

          <Pressable onPress={() => setManualEntry((prev) => !prev)} style={styles.manualLink}>
            <Text style={[styles.manualLinkText, { color: theme.colors.text }]}>
              {manualEntry ? 'Pick from the list instead' : 'Network not listed? Enter it by hand'}
            </Text>
          </Pressable>

          <Button
            title="Send to board"
            onPress={handleSendToBoard}
            disabled={!canSend}
            loading={sending}
            style={styles.primaryAction}
          />
        </>
      )}

      {step === 3 && (
        <>
          <ScreenHeader
            kicker="Step 3 of 3 · Check"
            title={checking ? `Checking ${scanResult.newBoard.id}…` : `${scanResult.newBoard.id} is online`}
          />

          <View style={styles.checkIconWrap}>
            {checking ? (
              <ActivityIndicator color={theme.colors.primary} size="large" />
            ) : (
              <View style={[styles.checkCircle, { backgroundColor: theme.colors.success + '33' }]}>
                <Feather name="check" size={32} color={theme.colors.success} />
              </View>
            )}
          </View>

          {!checking && health && (
            <View style={[styles.checklist, { backgroundColor: theme.colors.surface }]}>
              <ChecklistRow label="Bluetooth" value="Paired" />
              <ChecklistRow label="Wi-Fi" value={health.wifi} />
              <ChecklistRow label="Pivot server" value="Reachable" />
              <ChecklistRow label="Sensors" value={health.sensors} />
            </View>
          )}

          {!checking && (
            <>
              <TextInput
                label="Where is this board?"
                value={location}
                onChangeText={setLocation}
                placeholder="e.g. Studio C"
              />
              <Text style={[styles.scanHelper, { color: theme.colors.textSecondary, marginTop: -8 }]}>
                Shown to trainers when they pick a board for a session.
              </Text>

              <Button
                title="Calibrate the board"
                onPress={handleCalibrate}
                loading={saving}
                style={styles.primaryAction}
              />
              <Pressable onPress={handleSkip} disabled={saving} style={styles.skipLink}>
                <Text style={[styles.manualLinkText, { color: theme.colors.text }]}>Skip for now</Text>
              </Pressable>
            </>
          )}
        </>
      )}
    </ScreenContainer>
  );
}

function ChecklistRow({ label, value }) {
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
  scanCard: { borderRadius: 20, padding: 24, alignItems: 'center', marginBottom: 20 },
  bluetoothIcon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  scanTitle: { fontSize: 18, fontWeight: '700', marginBottom: 8 },
  scanHelper: { fontSize: 13, textAlign: 'center', lineHeight: 18 },
  scanSpinner: { marginTop: 16 },

  foundLabel: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5, marginBottom: 8 },
  boardRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 14, padding: 16, marginBottom: 10, borderWidth: 0 },
  boardRowHighlight: { borderWidth: 2 },
  boardRowText: { flex: 1, marginRight: 12 },
  boardRowTitle: { fontSize: 16, fontWeight: '700' },
  boardRowMeta: { fontSize: 12, marginTop: 2 },
  connectButton: { minHeight: 40, paddingHorizontal: 16, flexShrink: 0 },
  footerHelper: { fontSize: 12, textAlign: 'center', marginTop: 24 },

  connectedPill: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', borderRadius: 20, paddingVertical: 6, paddingHorizontal: 12, marginBottom: 16 },
  connectedDot: { width: 7, height: 7, borderRadius: 3.5 },
  connectedText: { fontSize: 13, fontWeight: '700' },

  manualLink: { marginBottom: 20 },
  manualLinkText: { fontSize: 14, fontWeight: '700', textDecorationLine: 'underline' },
  primaryAction: { marginTop: 4 },
  skipLink: { alignItems: 'center', marginTop: 16 },

  checkIconWrap: { alignItems: 'center', marginVertical: 24 },
  checkCircle: { width: 80, height: 80, borderRadius: 40, alignItems: 'center', justifyContent: 'center' },
  checklist: { borderRadius: 14, padding: 4, marginBottom: 20 },
  checklistRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 12, borderBottomWidth: 1 },
  checklistLabel: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
