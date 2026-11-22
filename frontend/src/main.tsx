import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import App from './App'
import { ToastProvider } from './components/ui'
import { AuthProvider } from './hooks'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'
import '@fontsource/dm-mono/400.css'
import '@fontsource/dm-mono/500.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import './styles/tokens.css'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: true,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TooltipPrimitive.Provider delayDuration={350}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </TooltipPrimitive.Provider>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
