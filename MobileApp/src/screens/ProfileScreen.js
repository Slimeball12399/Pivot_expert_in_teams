import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { DataActionRow } from '../components/DataActionRow';
import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { usePendingInvites } from '../hooks/usePendingInvites';
import { useProfileForm } from '../hooks/useProfileForm';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';
import { ageFromBirthDate } from '../utils/validators';
import { navy } from '../../assets/styles/colors';

function initials(user) {
  return `${user.first_name?.[0] ?? ''}${user.last_name?.[0] ?? ''}`.toUpperCase();
}

export function ProfileScreen() {
  const { theme } = useTheme();
  const { logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const {
    user,
    isSpeaker,
    editing,
    fields,
    setField,
    fieldErrors,
    formError,
    successMessage,
    submitting,
    startEditing,
    cancelEditing,
    handleSave,
  } = useProfileForm();
  const hasPendingInvites = usePendingInvites(isSpeaker);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  }

  function comingSoon() {
    Alert.alert('Coming soon', "This feature isn't available yet.");
  }

  if (!user) return null;

  const age = isSpeaker ? ageFromBirthDate(fields.birthDate) : null;
  const trainer = user.profile?.trainer;

  return (
    <ScreenContainer scroll>
      <View style={styles.titleRow}>
        <Text style={theme.styles.text.title}>Profile</Text>
        {isSpeaker && (
          <Pressable
            onPress={() => router.push('/invitations')}
            style={[styles.iconButton, { borderColor: theme.colors.primary }]}
          >
            <Feather name="mail" size={theme.sizes.icon.inContainer} color={theme.colors.primary} />
            {hasPendingInvites && (
              <View style={[styles.badge, { backgroundColor: theme.colors.danger, borderColor: theme.colors.surface }]} />
            )}
          </Pressable>
        )}
      </View>

      <View style={styles.identityRow}>
        <View style={[styles.avatar, { backgroundColor: theme.colors.accent }]}>
          <Text style={[theme.styles.text.heading, { color: navy }]}>{initials(user)}</Text>
        </View>
        <View>
          <Text style={[theme.styles.text.heading, { color: theme.colors.text }]}>
            {user.first_name} {user.last_name}
          </Text>
          {isSpeaker && (
            <Text style={[styles.trainerLine, { color: theme.colors.textSecondary }]}>
              {trainer ? `Trainer: ${trainer.first_name} ${trainer.last_name} – can see this profile` : 'Trainer: None'}
            </Text>
          )}
        </View>
      </View>

      <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
        <FormError message={formError} />
        <FormError message={!editing ? successMessage : null} tone="success" />

        <TextInput label="First name" value={fields.firstName} onChangeText={(v) => setField('firstName', v)} error={fieldErrors.firstName} editable={editing} />
        <TextInput label="Last name" value={fields.lastName} onChangeText={(v) => setField('lastName', v)} error={fieldErrors.lastName} editable={editing} />
        <TextInput label="Email" value={user.email} editable={false} />
        <TextInput
          label="Mobile number"
          value={fields.phoneNumber}
          onChangeText={(v) => setField('phoneNumber', v)}
          error={fieldErrors.phoneNumber}
          editable={editing}
          prefix="+45"
          keyboardType="phone-pad"
        />
        {isSpeaker && (
          <>
            <TextInput
              label="Date of birth"
              value={fields.birthDate}
              onChangeText={(v) => setField('birthDate', v)}
              error={fieldErrors.birthDate}
              editable={editing}
              placeholder="DD/MM/YYYY"
            />
            {age != null && (
              <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>Age: {age}</Text>
            )}
            <TextInput
              label="Height (cm)"
              value={fields.heightCm}
              onChangeText={(v) => setField('heightCm', v)}
              error={fieldErrors.heightCm}
              editable={editing}
              keyboardType="number-pad"
            />
            <Text style={[styles.helper, { color: theme.colors.textSecondary }]}>
              Helps us read your balance data correctly
            </Text>
            <TextInput
              label="What you want to get better at"
              value={fields.improvementGoals}
              onChangeText={(v) => setField('improvementGoals', v)}
              editable={editing}
              placeholder="e.g. Project more during presentations"
            />
          </>
        )}

        {editing ? (
          <>
            <Button title="Save changes" onPress={handleSave} loading={submitting} style={styles.action} />
            <Button title="Cancel" variant="outline" onPress={cancelEditing} disabled={submitting} style={styles.action} />
          </>
        ) : (
          <Button title="Edit profile" onPress={startEditing} style={styles.action} />
        )}
      </View>

      <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
        <Text style={[theme.styles.text.heading, styles.cardHeading, { color: theme.colors.text }]}>Account</Text>
        <Button
          title="Change password"
          variant="outline"
          onPress={() => router.push('/change-password')}
          style={styles.action}
        />
        <Button title="Log out" variant="outline" onPress={handleLogout} loading={loggingOut} style={styles.action} />
      </View>

      <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
        <Text style={[theme.styles.text.heading, styles.cardHeading, { color: theme.colors.text }]}>Your data</Text>
        <Text style={[styles.cardSubtitle, { color: theme.colors.textSecondary }]}>
          You decide what Pivot keeps. Each action asks you to confirm first.
        </Text>
        <DataActionRow
          icon="download"
          title="Download all my data"
          subtitle="Profile, scores, audio and board recordings"
          onPress={comingSoon}
        />
        <DataActionRow
          icon="eye-off"
          title="Anonymise my past sessions"
          subtitle="Removes your name and voice recordings, keeps the numbers"
          onPress={comingSoon}
        />
        <DataActionRow
          icon="trash-2"
          title="Delete my account"
          subtitle="Deletes all personal data for good"
          onPress={comingSoon}
          danger
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
  },
  identityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginTop: 20,
    marginBottom: 20,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  trainerLine: {
    fontSize: 12,
    marginTop: 2,
  },
  card: {
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
  },
  cardHeading: {
    marginBottom: 8,
  },
  cardSubtitle: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 16,
  },
  helper: {
    fontSize: 12,
    marginTop: -10,
    marginBottom: 16,
  },
  action: {
    marginTop: 8,
  },
});
