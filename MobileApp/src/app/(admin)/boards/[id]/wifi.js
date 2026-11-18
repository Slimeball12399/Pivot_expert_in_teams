import { useLocalSearchParams } from 'expo-router';

import { ChangeBoardWifiScreen } from '../../../../screens/ChangeBoardWifiScreen';

export default function Wifi() {
  const { id } = useLocalSearchParams();
  return <ChangeBoardWifiScreen boardId={id} />;
}
