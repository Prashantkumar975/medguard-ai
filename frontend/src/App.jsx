import { lazy } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import RequirePerm from './components/RequirePerm'
import { Empty } from './components/ui'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Sites = lazy(() => import('./pages/Sites'))
const SiteDetail = lazy(() => import('./pages/SiteDetail'))
const Queue = lazy(() => import('./pages/Queue'))
const Claims = lazy(() => import('./pages/Claims'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const Library = lazy(() => import('./pages/Library'))
const Reports = lazy(() => import('./pages/Reports'))
const Status = lazy(() => import('./pages/Status'))
const Notifications = lazy(() => import('./pages/Notifications'))
const AuditLog = lazy(() => import('./pages/AuditLog'))
const Help = lazy(() => import('./pages/Help'))
const Account = lazy(() => import('./pages/Account'))
const Admin = lazy(() => import('./pages/Admin'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route path="register" element={<Register />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="sites" element={<Sites />} />
        <Route path="sites/:id" element={<SiteDetail />} />
        <Route path="status" element={<Status />} />
        <Route path="reports" element={<Reports />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="help" element={<Help />} />
        <Route path="account" element={<Account />} />
        <Route path="queue" element={<Queue />} />
        <Route path="claims" element={<Claims />} />
        <Route path="incidents/:id" element={<IncidentDetail />} />
        <Route path="library" element={<Library />} />
        <Route path="admin" element={<RequirePerm perm="administer"><Admin /></RequirePerm>} />
        <Route
          path="*"
          element={
            <Empty title="Page not found" hint="Check the address, or go back to the dashboard.">
              <Link to="/" className="text-sm font-medium text-brand underline">Back to dashboard</Link>
            </Empty>
          }
        />
      </Route>
    </Routes>
  )
}
