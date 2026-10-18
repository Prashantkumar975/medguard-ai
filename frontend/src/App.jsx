import { lazy } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import RequirePerm from './components/RequirePerm'
import { Empty } from './components/ui'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Sites = lazy(() => import('./pages/Sites'))
const Queue = lazy(() => import('./pages/Queue'))
const Claims = lazy(() => import('./pages/Claims'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const Library = lazy(() => import('./pages/Library'))
const Admin = lazy(() => import('./pages/Admin'))

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="sites" element={<Sites />} />
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
