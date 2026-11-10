import { Feather } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { FormError } from '../components/FormError';
import { ScreenContainer } from '../components/ScreenContainer';
import { useProfileForm } from '../hooks/useProfileForm';
import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';
import { TextInput } from '../ui/TextInput';
import { ageFromBirthDate } from '../utils/validators';


const AVATAR_TEXT_COLOR = '#123048';

function initials(user) {
  return `${user.first_name?.[0] ?? ''}${user.last_name?.[0] ?? ''}`.toUpperCase();
}

function DataActionRow({ icon, title, subtitle, onPress, danger }) {
  const { theme } = useTheme();
  const textColor = danger ? '#ffffff' : theme.colors.text;
  const subtitleColor = danger ? 'rgba(255,255,255,0.85)' : theme.colors.textSecondary;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.dataRow,
        danger ? { backgroundColor: theme.colors.danger } : { borderWidth: 1, borderColor: theme.colors.border },
        pressed && { opacity: 0.85 },
      ]}
    >
      <Feather name={icon} size={20} color={textColor} />
      <View style={styles.dataRowText}>
        <Text style={[styles.dataRowTitle, { color: textColor }]}>{title}</Text>
        <Text style={[styles.dataRowSubtitle, { color: subtitleColor }]}>{subtitle}</Text>
      </View>
    </Pressable>
  );
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

  return (
    <ScreenContainer scroll>
      <Text style={theme.styles.text.title}>Profile</Text>

      <View style={styles.identityRow}>
        <View style={[styles.avatar, { backgroundColor: theme.colors.accent }]}>
          <Text style={[styles.avatarText, { color: AVATAR_TEXT_COLOR }]}>{initials(user)}</Text>
        </View>
        <Text style={[styles.name, { color: theme.colors.text }]}>
          {user.first_name} {user.last_name}
        </Text>
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
        <Text style={[styles.cardHeading, { color: theme.colors.text }]}>Account</Text>
        <Button
          title="Change password"
          variant="outline"
          onPress={() => router.push('/change-password')}
          style={styles.action}
        />
        <Button title="Log out" variant="outline" onPress={handleLogout} loading={loggingOut} style={styles.action} />
      </View>

      <View style={[styles.card, { backgroundColor: theme.colors.surface }]}>
        <Text style={[styles.cardHeading, { color: theme.colors.text }]}>Your data</Text>
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
  identityRow: { flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 20, marginBottom: 20 },
  avatar: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 18, fontWeight: '700' },
  name: { fontSize: 18, fontWeight: '700' },
  card: { borderRadius: 20, padding: 20, marginBottom: 20 },
  cardHeading: { fontSize: 18, fontWeight: '700', marginBottom: 8 },
  cardSubtitle: { fontSize: 13, lineHeight: 18, marginBottom: 16 },
  helper: { fontSize: 12, marginTop: -10, marginBottom: 16 },
  action: { marginTop: 8 },
  dataRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, borderRadius: 14, padding: 14, marginTop: 10 },
  dataRowText: { flex: 1 },
  dataRowTitle: { fontSize: 15, fontWeight: '700' },
  dataRowSubtitle: { fontSize: 12, marginTop: 2, lineHeight: 16 },
});
