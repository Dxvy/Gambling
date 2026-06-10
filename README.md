# SportPredict

AI-powered sports predictions and lottery tool. Next.js 16 frontend + FastAPI backend, authenticated via Supabase, deployed on Vercel + Railway.

---

## Architecture

```
Gambling/
├── sportpredict/
│   ├── frontend/        ← Next.js 16 app (React 19, Tailwind v4, Recharts)
│   ├── backend/         ← FastAPI + XGBoost prediction engine
│   ├── supabase/
│   │   └── migrations/  ← SQL schema (prediction_history, lottery_grids)
│   └── docs/
│       └── BUILD_APK.md ← Android build guide
└── .github/
    └── workflows/
        └── deploy.yml   ← CI/CD (Vercel + Railway on push to main)
```

---

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.12+
- **Git**

---

## Local development

### 1 — Clone

```bash
git clone https://github.com/Dxvy/Gambling.git
cd Gambling
```

### 2 — Backend

```bash
cd sportpredict/backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env .env   # fill in values (see Environment variables below)
uvicorn main:app --reload --port 8000
```

API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 3 — Frontend

```bash
cd sportpredict/frontend
npm install
cp .env.local .env.local   # fill in values
npm run dev
```

App is now available at `http://localhost:3000`.

---

## Environment variables

### Frontend (`sportpredict/frontend/.env.local`)

```env
NEXT_PUBLIC_SUPABASE_URL=https://<project-id>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Backend (`sportpredict/backend/.env`)

```env
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
```

---

## Database (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. In the SQL editor, run the migration:

```bash
# Paste contents of sportpredict/supabase/migrations/001_initial_schema.sql
```

This creates the `prediction_history` and `lottery_grids` tables with Row Level Security enabled.

3. Enable Google OAuth in **Authentication → Providers → Google** (requires a Google Cloud OAuth client ID/secret).

4. Set the redirect URL in **Authentication → URL Configuration**:
   - Local: `http://localhost:3000/auth/callback`
   - Production: `https://<your-app>.vercel.app/auth/callback`

---

## Deployment

### Frontend → Vercel

1. Import the repository in [vercel.com/new](https://vercel.com/new).
2. Set **Root Directory** to `sportpredict/frontend`.
3. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_BASE_URL` (your Railway backend URL)
4. Deploy.

### Backend → Railway

1. Create a new project in [railway.app](https://railway.app).
2. Add a service, connect this GitHub repository, and set **Root Directory** to `sportpredict/backend`.
3. Railway auto-detects `railway.json` and uses Nixpacks to build.
4. Add environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
5. Update `sportpredict/backend/main.py` CORS `allow_origins` with your Vercel URL.

### CI/CD (GitHub Actions)

The workflow in `.github/workflows/deploy.yml` deploys automatically on every push to `main`.

Add the following secrets to your GitHub repository (**Settings → Secrets and variables → Actions**):

| Secret | Where to get it |
|--------|----------------|
| `VERCEL_TOKEN` | vercel.com → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `vercel.json` output of `vercel link`, or project settings |
| `VERCEL_PROJECT_ID` | `vercel.json` output of `vercel link`, or project settings |
| `RAILWAY_TOKEN` | railway.app → Account Settings → Tokens |

---

## Android

See [`sportpredict/docs/BUILD_APK.md`](sportpredict/docs/BUILD_APK.md) for the full guide.

Quick start:

```bash
cd sportpredict/frontend
npx cap add android        # one-time setup
npm run build:android      # static export + cap sync
npm run open:android       # open Android Studio
```

`npm run build:android` sets `NEXT_STATIC_EXPORT=1` automatically, which switches Next.js to a fully-static `out/` build compatible with Capacitor. Regular `npm run build` (used by Vercel) uses the full Next.js server.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/sports/predict` | Match predictions |
| GET | `/api/sports/matches` | Upcoming matches |
| POST | `/api/lottery/generate` | Generate lottery grid |

Full docs available at `/docs` when the backend is running.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | Next.js 16 (React 19, App Router) |
| Styling | Tailwind CSS v4 |
| Charts | Recharts v3 |
| Auth | Supabase Auth (Google OAuth + email) |
| Database | Supabase (PostgreSQL + Row Level Security) |
| Backend | FastAPI + uvicorn |
| ML model | XGBoost + scikit-learn |
| Mobile | Capacitor 8 (Android) |
| Frontend hosting | Vercel |
| Backend hosting | Railway |
