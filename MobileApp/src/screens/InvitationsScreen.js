import { Feather } from '@expo/vector-icons';
import { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useInvitations } from '../hooks/useInvitations';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

// Navy, fixed regardless of theme — same reasoning as ProfileScreen's avatar.
const AVATAR_TEXT_COLOR = '#123048';

function formatExpiry(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function trainerInitials(name) {
  return (name || '').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase();
}

export function InvitationsScreen() {
  const { theme } = useTheme();
  const {
    invites, currentTrainer, loading, loadError,
    acceptingId, acceptError, successMessage, accept, clearAcceptError,
  } = useInvitations();
  const [selectedInvite, setSelectedInvite] = useState(null);

  function openInvite(invite) {
    clearAcceptError();
    setSelectedInvite(invite);
  }

  async function handleAccept() {
    const ok = await accept(selectedInvite);
    if (ok) setSelectedInvite(null);
  }

  return (
    <ScreenContainer scroll>
      <Text style={theme.styles.text.title}>Invitations</Text>
      {currentTrainer && (
        <Text style={[styles.subtitle, { color: theme.colors.textSecondary }]}>
          Current trainer: {currentTrainer}
        </Text>
      )}

      <FormError message={loadError} />
      <FormError message={!selectedInvite ? successMessage : null} tone="success" />

      {loading ? (
        <ActivityIndicator color={theme.colors.primary} style={styles.spinner} />
      ) : invites.length === 0 ? (
        <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
          <Text style={[styles.emptyText, { color: theme.colors.textSecondary }]}>
            You don&apos;t have any pending invitations.
          </Text>
        </View>
      ) : (
        invites.map((invite) => (
          <Pressable
            key={invite.id}
            onPress={() => openInvite(invite)}
            style={[styles.card, styles.row, { backgroundColor: theme.colors.surface }]}
          >
            <View>
              <Text style={[styles.trainerName, { color: theme.colors.text }]}>{invite.trainerName}</Text>
              <Text style={[styles.expiry, { color: theme.colors.textSecondary }]}>
                Expires {formatExpiry(invite.expiresAt)}
              </Text>
            </View>
            <Feather name="chevron-right" size={20} color={theme.colors.textSecondary} />
          </Pressable>
        ))
      )}

      <Modal
        visible={!!selectedInvite}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedInvite(null)}
      >
        <View style={styles.modalRoot}>
          <Pressable style={styles.backdrop} onPress={() => setSelectedInvite(null)} />
          {selectedInvite && (
            <View style={[styles.sheet, { backgroundColor: theme.colors.surface }]}>
              <View style={[styles.handle, { backgroundColor: theme.colors.border }]} />

              <View style={styles.sheetHeader}>
                <View style={[styles.avatar, { backgroundColor: theme.colors.accent }]}>
                  <Text style={[styles.avatarText, { color: AVATAR_TEXT_COLOR }]}>
                    {trainerInitials(selectedInvite.trainerName)}
                  </Text>
                </View>
                <View style={styles.sheetHeaderText}>
                  <Text style={[styles.sheetTitle, { color: theme.colors.text }]}>
                    {selectedInvite.trainerName} invited you
                  </Text>
                  <Text style={[styles.sheetSubtitle, { color: theme.colors.textSecondary }]}>
                    Expires {formatExpiry(selectedInvite.expiresAt)}
                  </Text>
                </View>
              </View>

              <View style={[styles.infoBox, { backgroundColor: theme.colors.background }]}>
                <View style={styles.infoRow}>
                  <Text style={[styles.infoLabel, { color: theme.colors.textSecondary }]}>Trainer</Text>
                  <Text style={[styles.infoValue, { color: theme.colors.text }]}>
                    {selectedInvite.trainerName}
                  </Text>
                </View>
                <View style={styles.infoRow}>
                  <Text style={[styles.infoLabel, { color: theme.colors.textSecondary }]}>Expires</Text>
                  <Text style={[styles.infoValue, { color: theme.colors.text }]}>
                    {formatExpiry(selectedInvite.expiresAt)}
                  </Text>
                </View>
                {currentTrainer && (
                  <View style={[styles.infoRow, styles.infoRowLast]}>
                    <Text style={[styles.infoLabel, { color: theme.colors.textSecondary }]}>Current trainer</Text>
                    <Text style={[styles.infoValue, { color: theme.colors.text }]}>{currentTrainer}</Text>
                  </View>
                )}
              </View>

              <Text style={[styles.sheetBody, { color: theme.colors.textSecondary }]}>
                {currentTrainer
                  ? `Accepting will replace ${currentTrainer} as your trainer.`
                  : `Accepting makes ${selectedInvite.trainerName} your trainer.`}
              </Text>

              <FormError message={acceptError} />

              <Button
                title={currentTrainer ? 'Replace and accept' : 'Accept invitation'}
                onPress={handleAccept}
                loading={acceptingId === selectedInvite.id}
              />
              <Pressable onPress={() => setSelectedInvite(null)} style={styles.notNow}>
                <Text style={[styles.notNowText, { color: theme.colors.text }]}>Not now</Text>
              </Pressable>
            </View>
          )}
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { fontSize: 14, marginTop: 8 },
  spinner: { marginTop: 24 },
  card: { borderRadius: 20, padding: 20, marginTop: 20 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  emptyText: { fontSize: 14, textAlign: 'center' },
  trainerName: { fontSize: 18, fontWeight: '700' },
  expiry: { fontSize: 13, marginTop: 4 },

  modalRoot: { flex: 1 },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)' },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 36,
  },
  handle: { width: 36, height: 4, borderRadius: 2, alignSelf: 'center', marginBottom: 20 },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 20 },
  avatar: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 16, fontWeight: '700' },
  sheetHeaderText: { flex: 1 },
  sheetTitle: { fontSize: 18, fontWeight: '700' },
  sheetSubtitle: { fontSize: 13, marginTop: 2 },
  infoBox: { borderRadius: 14, padding: 16, marginBottom: 16 },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  infoRowLast: { marginBottom: 0 },
  infoLabel: { fontSize: 13 },
  infoValue: { fontSize: 13, fontWeight: '700' },
  sheetBody: { fontSize: 13, lineHeight: 18, marginBottom: 20 },
  notNow: { marginTop: 16, alignItems: 'center' },
  notNowText: { fontSize: 15, fontWeight: '700', textDecorationLine: 'underline' },
});
