import { useLocalSearchParams } from 'expo-router';

import { UserDetailScreen } from '../../screens/UserDetailScreen';

export default function UserDetail() {
  const { id } = useLocalSearchParams();
  return <UserDetailScreen userId={id} />;
}
