import { useLocalSearchParams } from 'expo-router';

import { CalibrateBoardScreen } from '../../../../screens/CalibrateBoardScreen';

export default function Calibrate() {
  const { id, location } = useLocalSearchParams();
  return <CalibrateBoardScreen boardId={id} location={location} />;
}
