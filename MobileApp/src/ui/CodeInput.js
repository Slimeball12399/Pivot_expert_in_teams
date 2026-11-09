import { useRef } from 'react';
import { StyleSheet, TextInput as RNTextInput, View } from 'react-native';

import { useTheme } from '../providers/ThemeProvider';

export function CodeInput({ length, value, onChangeText, error }) {
  const { theme } = useTheme();
  const { colors } = theme;
  const inputs = useRef([]);

  function handleChangeText(index, text) {
    const digits = text.replace(/\D/g, '');
    const next = value.split('');

    if (!digits) {
      next[index] = '';
      onChangeText(next.join(''));
      return;
    }

    for (let i = 0; i < digits.length && index + i < length; i++) {
      next[index + i] = digits[i];
    }
    onChangeText(next.join('').slice(0, length));

    const lastFilled = Math.min(index + digits.length, length) - 1;
    if (lastFilled < length - 1) inputs.current[lastFilled + 1]?.focus();
    else inputs.current[lastFilled]?.blur();
  }

  function handleKeyPress(index, e) {
    if (e.nativeEvent.key === 'Backspace' && !value[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
  }

  return (
    <View style={styles.row}>
      {Array.from({ length }).map((_, i) => (
        <RNTextInput
          key={i}
          ref={(el) => { inputs.current[i] = el; }}
          value={value[i] || ''}
          onChangeText={(text) => handleChangeText(i, text)}
          onKeyPress={(e) => handleKeyPress(i, e)}
          keyboardType="number-pad"
          maxLength={2} 
          textAlign="center"
          style={[
            styles.box,
            {
              backgroundColor: colors.surface,
              borderColor: error ? colors.danger : colors.border,
              color: colors.text,
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  box: {
    width: 34,
    height: 48,
    borderWidth: 1,
    borderRadius: 10,
    fontSize: 20,
    fontWeight: '700',
  },
});
