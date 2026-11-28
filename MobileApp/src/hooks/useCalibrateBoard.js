import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Alert } from 'react-native';

import { measureCalibrationStep, saveCalibration } from '../api/boards';

export const HOLD_SECONDS = 2;
export const DIRECTIONS = ['left', 'right', 'front', 'back'];

// Owns CalibrateBoardScreen's rest-reading
export function useCalibrateBoard(boardId) {
  const [restDone, setRestDone] = useState(false);
  const [measurements, setMeasurements] = useState({ left: null, right: null, front: null, back: null });
  const [holding, setHolding] = useState(false);
  const [holdSeconds, setHoldSeconds] = useState(0);
  const [saving, setSaving] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    const timer = setTimeout(() => setRestDone(true), 1200);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => () => clearInterval(intervalRef.current), []);

  const currentDirection = DIRECTIONS.find((direction) => measurements[direction] == null);
  const allMeasured = restDone && !currentDirection;
  const measuredCount = DIRECTIONS.filter((direction) => measurements[direction] != null).length;

  async function handleHold() {
    setHolding(true);
    setHoldSeconds(0);
    intervalRef.current = setInterval(() => {
      setHoldSeconds((prev) => Math.min(prev + 1, HOLD_SECONDS));
    }, 1000);

    try {
      const result = await measureCalibrationStep(boardId, currentDirection);
      setMeasurements((prev) => ({ ...prev, [currentDirection]: result.stopAngle }));
    } catch {
      Alert.alert('Could not measure this direction', 'Check your connection and try again.');
    } finally {
      clearInterval(intervalRef.current);
      setHolding(false);
      setHoldSeconds(0);
    }
  }

  function handleStartAgain() {
    clearInterval(intervalRef.current);
    setHolding(false);
    setMeasurements({ left: null, right: null, front: null, back: null });
  }

  async function handleSave() {
    setSaving(true);
    try {
      await saveCalibration(boardId);
      router.replace('/(admin)/boards');
    } catch {
      Alert.alert('Could not save calibration', 'Check your connection and try again.');
    } finally {
      setSaving(false);
    }
  }

  return {
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
  };
}
