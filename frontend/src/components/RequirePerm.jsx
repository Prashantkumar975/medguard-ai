import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Card, Empty } from './ui'

// Wrap a route element. Renders children only if the current role has the permission.
export default function RequirePerm({ perm, children }) {
  const { can } = useAuth()
  if (can(perm)) return children
  return (
    <Card>
      <Empty title="You don't have access to this page" hint="Ask an administrator to change your role if you need it.">
        <Link to="/" className="text-sm font-medium text-brand underline">Back to dashboard</Link>
      </Empty>
    </Card>
  )
}
