import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { BottomSheet } from '../components/BottomSheet';
import { InviteRow } from '../components/InviteRow';
import { InviteRowSkeleton } from '../components/InviteRowSkeleton';
import { LoadErrorState } from '../components/LoadErrorState';
import { ScreenContainer } from '../components/ScreenContainer';
import { useInvitations } from '../hooks/useInvitations';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { formatExpiry, initialsFromName } from '../utils/format';

// Navy, fixed regardless of theme — same reasoning as ProfileScreen's avatar.
const AVATAR_TEXT_COLOR = '#123048';

export function InvitationsScreen() {
  const { theme } = useTheme();
  const { invites, currentTrainer, loading, loadError, acceptingId, accept } = useInvitations();
  const [selectedInvite, setSelectedInvite] = useState(null);

  function openInvite(invite) {
    setSelectedInvite(invite);
  }

  async function handleAccept() {
    const { ok, message } = await accept(selectedInvite);
    if (ok) {
      setSelectedInvite(null);
      Alert.alert('Trainer updated', message);
    } else {
      Alert.alert('Could not accept invitation', message);
    }
  }

  return (
    <ScreenContainer scroll>
      <Text style={theme.styles.text.title}>Invitations</Text>
      {currentTrainer && (
        <Text style={[styles.subtitle, { color: theme.colors.textSecondary }]}>
          Current trainer: {currentTrainer}
        </Text>
      )}

      {loadError ? (
        <LoadErrorState message={loadError} />
      ) : loading ? (
        <>
          <InviteRowSkeleton />
          <InviteRowSkeleton />
          <InviteRowSkeleton />
        </>
      ) : invites.length === 0 ? (
        <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
          <Text style={[styles.emptyText, { color: theme.colors.textSecondary }]}>
            You don&apos;t have any pending invitations.
          </Text>
        </View>
      ) : (
        invites.map((invite) => (
          <InviteRow key={invite.id} invite={invite} onPress={() => openInvite(invite)} />
        ))
      )}

      <BottomSheet visible={!!selectedInvite} onClose={() => setSelectedInvite(null)}>
        {selectedInvite && (
          <>
            <View style={styles.sheetHeader}>
              <View style={[styles.avatar, { backgroundColor: theme.colors.accent }]}>
                <Text style={[styles.avatarText, { color: AVATAR_TEXT_COLOR }]}>
                  {initialsFromName(selectedInvite.trainerName)}
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
              {selectedInvite.replacesTrainerName && (
                <View style={[styles.infoRow, styles.infoRowLast]}>
                  <Text style={[styles.infoLabel, { color: theme.colors.textSecondary }]}>Current trainer</Text>
                  <Text style={[styles.infoValue, { color: theme.colors.text }]}>
                    {selectedInvite.replacesTrainerName}
                  </Text>
                </View>
              )}
            </View>

            <Text style={[styles.sheetBody, { color: theme.colors.textSecondary }]}>
              {selectedInvite.replacesTrainerName
                ? `Accepting will replace ${selectedInvite.replacesTrainerName} with `
                  + `${selectedInvite.trainerName} as your trainer.`
                : `Accepting makes ${selectedInvite.trainerName} your trainer.`}
            </Text>

            <Button
              title={selectedInvite.replacesTrainerName ? 'Replace and accept' : 'Accept invitation'}
              onPress={handleAccept}
              loading={acceptingId === selectedInvite.id}
            />
            <Pressable onPress={() => setSelectedInvite(null)} style={styles.notNow}>
              <Text style={[styles.notNowText, { color: theme.colors.text }]}>Not now</Text>
            </Pressable>
          </>
        )}
      </BottomSheet>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: {
    fontSize: 14,
    marginTop: 8,
  },
  card: {
    borderRadius: 20,
    padding: 20,
    marginTop: 20,
  },
  emptyText: {
    fontSize: 14,
    textAlign: 'center',
  },

  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginBottom: 20,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 16,
    fontWeight: '700',
  },
  sheetHeaderText: {
    flex: 1,
  },
  sheetTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  sheetSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  infoBox: {
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  infoRowLast: {
    marginBottom: 0,
  },
  infoLabel: {
    fontSize: 13,
  },
  infoValue: {
    fontSize: 13,
    fontWeight: '700',
  },
  sheetBody: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 20,
  },
  notNow: {
    marginTop: 16,
    alignItems: 'center',
  },
  notNowText: {
    fontSize: 15,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
});
