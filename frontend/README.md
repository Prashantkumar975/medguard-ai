# MedGuard AI Frontend

React 18, Vite, Tailwind CSS, React Router, and TanStack Query.

## Run with real account authentication

1. Start the backend API at `http://localhost:8000` and initialize its database and administrator account. See [`../backend/README.md`](../backend/README.md).
2. Copy `.env.example` to `.env` and set `VITE_API_URL` if the backend is hosted elsewhere. Keep `VITE_USE_MOCK=false` for real account authentication.
3. Install dependencies and start the frontend:

   ```powershell
   npm install
   npm run dev
   ```

Open `http://localhost:5173/login`. Sign-in uses the backend `/api/v1/auth/login` endpoint. Select **Create an account** to register a workspace and its first administrator through `/api/v1/auth/register`. Registration currently does not verify email ownership. If an email is used in more than one organization, enter the organization ID shown on the Account page. The frontend validates the session through `/auth/me`, refreshes expired access tokens, and revokes the refresh token on logout.

## Demo mode

Set `VITE_USE_MOCK=true` to use the fictional in-memory sample data. Any non-empty email and password will open the demo workspace; this is not real authentication and must not be used for protected data.
