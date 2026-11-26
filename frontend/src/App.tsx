import { useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { applyBrandMetadata } from './config/brand'
import { AppErrorBoundary } from './components/layout/AppErrorBoundary'
import { AppShell } from './components/layout/AppShell'
import { AdminRoute, PlayerHomeRoute, ProtectedRoute } from './components/auth/RouteGuards'
import { ErrorPage } from './pages/ErrorPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { StatusPage } from './pages/StatusPage'
import { LoginPage, ProfilePage, RegisterPage } from './pages'
import { TeamOnboardingPage } from './pages/TeamOnboardingPage'
import { TeamPage } from './pages/TeamPage'
import { TeamsPage } from './pages/TeamsPage'
import { AdminEventPage } from './pages/AdminEventPage'
import { ChallengesPage } from './pages/ChallengesPage'
import { AdminChallengesPage } from './pages/AdminChallengesPage'
import { AdminChallengeEditorPage } from './pages/AdminChallengeEditorPage'
import { AdminCategoriesPage } from './pages/AdminCategoriesPage'
import { AdminChallengeHealthPage } from './pages/AdminChallengeHealthPage'

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
            <Route element={<PlayerHomeRoute />}>
              <Route index element={<StatusPage />} />
            </Route>
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route path="teams" element={<TeamsPage />} />
            <Route path="teams/:id" element={<TeamPage />} />
            <Route element={<ProtectedRoute allowNoTeam />}>
              <Route path="team/onboarding" element={<TeamOnboardingPage />} />
              <Route path="team" element={<TeamPage />} />
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route path="challenges" element={<ChallengesPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>
            <Route element={<AdminRoute />}>
              <Route path="admin/event" element={<AdminEventPage />} />
              <Route path="admin/challenges" element={<AdminChallengesPage />} />
              <Route path="admin/challenges/health" element={<AdminChallengeHealthPage />} />
              <Route path="admin/challenges/new" element={<AdminChallengeEditorPage />} />
              <Route path="admin/challenges/:id/edit" element={<AdminChallengeEditorPage />} />
              <Route path="admin/categories" element={<AdminCategoriesPage />} />
            </Route>
            <Route path="error" element={<ErrorPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AppErrorBoundary>
    </BrowserRouter>
  )
}
