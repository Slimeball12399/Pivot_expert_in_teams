import { EmptyProvider } from './EmptyProvider';
import { ThemeProvider } from './ThemeProvider';

// Every app-wide provider is composed here, so the root layout stays small.
// Add new providers inside ThemeProvider so they can use the theme.
export function AppProviders({ children }) {
  return (
    <ThemeProvider>
      <EmptyProvider>{children}</EmptyProvider>
    </ThemeProvider>
  );
}
