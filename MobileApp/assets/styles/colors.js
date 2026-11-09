// Color tokens shared with the web app's design system

const navy = '#123048';
const rose = '#e3b7cb';
const paper = '#f0f0f0';

export const feedback = {
  success: '#5cbf8d',
  warning: '#c09b27',
  error: '#f03f41',
  info: '#183b89',
  unassigned: '#824299', // not assigned to anything yet, per the design system
};

export const dark = {
  background: navy,
  surface: '#1c3e5c',
  primary: rose,
  primaryText: navy,
  text: paper,
  textSecondary: '#9fb3c4',
  border: '#2c4a68',
  placeholder: '#6f8aa0',
  danger: feedback.error,
  accent: rose,
};

export const light = {
  background: paper,
  surface: '#ffffff',
  primary: navy,
  primaryText: paper,
  text: navy,
  textSecondary: '#51708c',
  border: '#d4d4d4',
  placeholder: '#8a8a8a',
  danger: feedback.error,
  accent: rose,
};
