# MedGuard AI frontend

React 18 + Vite + Tailwind 4 (plain JSX). Routing: React Router. Data: TanStack Query.

## Run
    npm install
    npm run dev        # http://localhost:5173

## Connect to the real backend (for the backend teammate)
1. In `.env` set `VITE_USE_MOCK=false` and `VITE_API_URL=http://localhost:8000`.
2. All calls go through `src/api/endpoints.js` and `src/api/client.js`. Requests are sent to `{VITE_API_URL}/api/v1/...` with `Authorization: Bearer <localStorage.mg_token>`.
3. `src/api/mock.js` is the contract: the JSON shapes it returns are what each page expects.
4. Replace `src/auth/AuthContext.jsx` with the real session (roles: admin, reviewer, viewer). The "Preview as role" switcher only shows in mock mode.

## Endpoints used
In the plan: GET/POST /sites, POST /scans, GET /scans/{id}, GET /claims, GET /incidents, GET /incidents/{id},
POST /incidents/{id}/review (body: decision = confirm | dismiss | needs_info, rationale), POST /incidents/{id}/recheck, GET /analytics/summary.

Not in the plan, needed by the UI (proposed):
- GET /scans?site_id=    crawl history
- PATCH /sites/{id}      enable or disable a site
- GET /references?q=     Medical library
- GET /admin/users, PATCH /admin/users/{id}, GET/PUT /admin/settings

Query params for GET /incidents: q, priority, verdict, status (active | all | a single status).
