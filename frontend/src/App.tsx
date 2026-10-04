import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RequireAuth, RequireRole } from './components/RouteGuards'
import { Spinner } from './components/Skeleton'
import { AuthProvider } from './context/AuthProvider'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ROUTE_ROLES } from './utils/navigation'

// Route-level code splitting keeps the initial bundle small (charts load only where used).
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const PatientsPage = lazy(() => import('./pages/PatientsPage').then((m) => ({ default: m.PatientsPage })))
const AppointmentsPage = lazy(() => import('./pages/AppointmentsPage').then((m) => ({ default: m.AppointmentsPage })))
const BedsPage = lazy(() => import('./pages/BedsPage').then((m) => ({ default: m.BedsPage })))
const StaffPage = lazy(() => import('./pages/StaffPage').then((m) => ({ default: m.StaffPage })))
const EmergencyPage = lazy(() => import('./pages/EmergencyPage').then((m) => ({ default: m.EmergencyPage })))
const AssistantPage = lazy(() => import('./pages/AssistantPage').then((m) => ({ default: m.AssistantPage })))

function guarded(path: string, element: ReactNode) {
  return (
    <RequireRole roles={ROUTE_ROLES[path]}>
      <Suspense
        fallback={
          <div className="flex justify-center py-24">
            <Spinner label="Loading page" size={28} />
          </div>
        }
      >
        {element}
      </Suspense>
    </RequireRole>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={guarded('/', <DashboardPage />)} />
            <Route path="patients" element={guarded('/patients', <PatientsPage />)} />
            <Route path="appointments" element={guarded('/appointments', <AppointmentsPage />)} />
            <Route path="beds" element={guarded('/beds', <BedsPage />)} />
            <Route path="staff" element={guarded('/staff', <StaffPage />)} />
            <Route path="emergency" element={guarded('/emergency', <EmergencyPage />)} />
            <Route path="assistant" element={guarded('/assistant', <AssistantPage />)} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
