import { useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { applyBrandMetadata } from './config/brand'
import { AppErrorBoundary } from './components/layout/AppErrorBoundary'
import { AppShell } from './components/layout/AppShell'
import { ErrorPage } from './pages/ErrorPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { StatusPage } from './pages/StatusPage'

function BrandMetadata() {
  useEffect(() => {
    applyBrandMetadata()
  }, [])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <BrandMetadata />
      <AppErrorBoundary>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<StatusPage />} />
            <Route path="error" element={<ErrorPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AppErrorBoundary>
    </BrowserRouter>
  )
}
