import '@fontsource/wix-madefor-text/400.css';
import '@fontsource/wix-madefor-text/500.css';
import '@fontsource/wix-madefor-text/600.css';
import '@fontsource/wix-madefor-text/700.css';
import '@fontsource/wix-madefor-display/600.css';
import '@fontsource/wix-madefor-display/700.css';
import '@mantine/core/styles.css';
import '@mantine/dropzone/styles.css';
import '@mantine/notifications/styles.css';
import './styles.css';

import { MantineProvider, type CSSVariablesResolver } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { ApiError } from './api/client';
import { AuthProvider } from './auth/AuthContext';
import { theme } from './theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

/** Нейтральные цвета текста и фона Mantine — под токены из styles.css. */
const resolver: CSSVariablesResolver = () => ({
  variables: {},
  light: {
    '--mantine-color-body': '#ffffff',
    '--mantine-color-text': '#0e0f11',
    '--mantine-color-dimmed': '#747883',
    '--mantine-color-default-border': '#e6e8ec',
    '--mantine-color-placeholder': '#9a9ea7',
  },
  dark: {},
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme} cssVariablesResolver={resolver} forceColorScheme="light">
      <Notifications position="top-right" />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
