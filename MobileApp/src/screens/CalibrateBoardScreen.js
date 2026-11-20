import { router } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { CalibrationCompass } from '../components/CalibrationCompass';
import { ProgressBar } from '../components/ProgressBar';
import { ScreenContainer } from '../components/ScreenContainer';
import { ScreenHeader } from '../components/ScreenHeader';
import { StatusPill } from '../components/StatusPill';
import { DIRECTIONS, HOLD_SECONDS, useCalibrateBoard } from '../hooks/useCalibrateBoard';
import { useTheme } from '../providers/ThemeProvider';
import { Button } from '../ui/Button';

const DIRECTION_LABEL = { left: 'Left', right: 'Right', front: 'Front', back: 'Back' };
const DIRECTION_PROMPT = {
  left: 'Tilt all the way to the left.',
  right: 'Tilt all the way to the right.',
  front: 'Tilt all the way to the front.',
  back: 'Tilt all the way to the back.',
};

export function CalibrateBoardScreen({ boardId, location }) {
  const { theme } = useTheme();
  const {
    restDone,
    measurements,
    holding,
    holdSeconds,
    saving,
    currentDirection,
    allMeasured,
    measuredCount,
    handleHold,
    handleStartAgain,
    handleSave,
  } = useCalibrateBoard(boardId);

  return (
    <ScreenContainer scroll>
      <ScreenHeader
        kicker={`${boardId} · ${location}`}
        title="Calibrate the board"
        onBack={() => router.replace('/(admin)/boards')}
      />

      <View style={styles.pillRow}>
        <StatusPill state={restDone ? 'done' : 'active'} label="1 · Level at rest" />
        <StatusPill
          state={allMeasured ? 'done' : restDone ? 'active' : 'pending'}
          label={`2 · Full tilt range${restDone ? ` · ${measuredCount} of 4` : ''}`}
        />
      </View>

      {!restDone ? (
        <View style={styles.restWait}>
          <ActivityIndicator color={theme.colors.primary} />
          <Text style={[styles.restWaitText, { color: theme.colors.textSecondary }]}>
            Keep the board flat and still — reading its zero point.
          </Text>
        </View>
      ) : (
        <>
          {currentDirection && (
            <View style={[styles.stepCard, { backgroundColor: theme.colors.surface }]}>
              <CalibrationCompass measurements={measurements} currentDirection={currentDirection} pulsing={holding} />
              <View style={styles.stepCardText}>
                <Text style={[styles.stepCardKicker, { color: theme.colors.textSecondary }]}>
                  NOW · {DIRECTIONS.indexOf(currentDirection) + 1} OF 4
                </Text>
                <Text style={[styles.stepCardTitle, { color: theme.colors.text }]}>
                  {DIRECTION_PROMPT[currentDirection]}
                </Text>
                <Text style={[styles.stepCardHelper, { color: theme.colors.textSecondary }]}>
                  Keep going until the board stops, then hold.
                </Text>
              </View>
            </View>
          )}

          <View style={[styles.list, { backgroundColor: theme.colors.surface }]}>
            {DIRECTIONS.map((direction, index) => (
              <View
                key={direction}
                style={[styles.listRow, index > 0 && { borderTopWidth: 1, borderTopColor: theme.colors.border }]}
              >
                <View style={styles.listLabel}>
                  <View
                    style={[
                      styles.listDot,
                      {
                        backgroundColor: measurements[direction] != null
                          ? theme.colors.success
                          : direction === currentDirection
                            ? theme.colors.primary
                            : theme.colors.border,
                      },
                    ]}
                  />
                  <Text style={{ color: theme.colors.text, fontWeight: direction === currentDirection ? '700' : '400' }}>
                    {DIRECTION_LABEL[direction]}
                  </Text>
                </View>
                <Text style={{ color: measurements[direction] != null ? theme.colors.success : theme.colors.textSecondary }}>
                  {measurements[direction] != null
                    ? `Stop at ${measurements[direction]}°`
                    : direction === currentDirection
                      ? (holding ? 'Measuring' : 'Ready')
                      : 'Next'}
                </Text>
              </View>
            ))}
          </View>

          {currentDirection && (
            <>
              <Text style={[styles.holdLabel, { color: theme.colors.text }]}>
                {holding ? 'Board stopped · hold' : 'Hold the board still at the end of its tilt'}
                {holding && <Text style={{ color: theme.colors.textSecondary }}>   {holdSeconds} of {HOLD_SECONDS} s</Text>}
              </Text>
              {holding && (
                <ProgressBar progress={holdSeconds / HOLD_SECONDS} style={styles.progressSpacing} />
              )}
              <Text style={[styles.calibrationNote, { color: theme.colors.textSecondary }]}>
                Calibration data is never counted in anyone&apos;s progress.
              </Text>
              <Button
                title={holding ? 'Measuring…' : `I'm holding it at the ${DIRECTION_LABEL[currentDirection].toLowerCase()}`}
                onPress={handleHold}
                loading={holding}
                style={styles.holdButton}
              />
            </>
          )}

          <Button
            title={allMeasured ? 'Save calibration' : 'Save calibration · after all 4'}
            onPress={handleSave}
            disabled={!allMeasured}
            loading={saving}
            style={styles.saveButton}
          />
          <Button title="Start again" variant="outline" onPress={handleStartAgain} disabled={holding || saving} />
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  pillRow: { flexDirection: 'row', gap: 10, marginVertical: 20 },
  restWait: { alignItems: 'center', marginTop: 40 },
  restWaitText: { fontSize: 13, textAlign: 'center', marginTop: 16 },

  stepCard: { flexDirection: 'row', gap: 16, borderRadius: 18, padding: 18, marginBottom: 16, alignItems: 'center' },
  stepCardText: { flex: 1 },
  stepCardKicker: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5, marginBottom: 4 },
  stepCardTitle: { fontSize: 18, fontWeight: '700', marginBottom: 4 },
  stepCardHelper: { fontSize: 13 },

  list: { borderRadius: 14, marginBottom: 16 },
  listRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 14 },
  listLabel: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  listDot: { width: 9, height: 9, borderRadius: 4.5 },

  holdLabel: { fontSize: 14, fontWeight: '700', marginBottom: 8 },
  progressSpacing: { marginBottom: 12 },
  calibrationNote: { fontSize: 12, marginBottom: 16 },
  holdButton: { marginBottom: 20 },
  saveButton: { marginBottom: 10 },
});
