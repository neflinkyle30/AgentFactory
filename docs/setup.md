# Agent Factory OSS — Setup Guide

## Prerequisites

| Dependency | Minimum Version | Check |
|------------|----------------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 20+ | `node --version` |
| PostgreSQL | 16+ | `psql --version` |
| Git | 2.40+ | `git --version` |
| Docker (optional) | 24+ | `docker --version` |

### Optional CLI Tools (for Git providers)

| Tool | Provider | Install |
|------|----------|---------|
| `gh` | GitHub | `winget install GitHub.cli` (or https://cli.github.com) |
| `glab` | GitLab | `winget install GitLab.GitLabCLI` (or https://gitlab.com/gitlab-org/cli) |

## Quickstart (Docker Compose)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/agent-factory.git
cd agent-factory

# 2. Create environment file
cp .env.example .env
# Edit .env — set DEEPSEEK_API_KEY and JWT_SECRET

# 3. Start all services
docker compose up -d

# 4. Verify
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}

# 5. Open the dashboard
# http://localhost:3000
```

## Manual Setup

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Activate (Unix/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # For testing tools

# Configure environment
cp ../.env.example ../.env
# Edit ../.env with your settings

# Initialize database
alembic upgrade head

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# → http://localhost:3000

# The dev server proxies /api/* to localhost:8000
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# ── Mode Flags ──────────────────────────────────────
AGENT_FACTORY_DEV=0        # 1 = SQLite (no PostgreSQL needed)
AGENT_FACTORY_MOCK=0       # 1 = Mock AI (no API calls, for testing)

# ── Database ────────────────────────────────────────
# PostgreSQL (default)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentfactory

# SQLite (when AGENT_FACTORY_DEV=1)
# Automatically uses sqlite+aiosqlite:///agentfactory.db

# ── DeepSeek API ────────────────────────────────────
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ── JWT Authentication ──────────────────────────────
JWT_SECRET=change-me-in-production-use-a-long-random-string
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"

# ── CORS ────────────────────────────────────────────
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# ── Optional ────────────────────────────────────────
RUNS_DIRECTORY=runs
DEFAULT_BUDGET_LIMIT_USD=0.0    # 0 = unlimited
HITL_ENABLED_DEFAULT=true       # HITL pause before PR creation
```

## Development Mode

For quick local development without PostgreSQL:

```bash
# Backend: SQLite + Mock AI
AGENT_FACTORY_DEV=1 AGENT_FACTORY_MOCK=1 uvicorn app.main:app --reload --port 8000
```

This mode:
- Uses SQLite (no PostgreSQL needed)
- Uses MockProvider (no DeepSeek API key needed)
- Returns deterministic canned responses per role
- Perfect for frontend development and pipeline testing

## Running Tests

```bash
# Backend tests
cd backend
pip install -e ".[dev]"
python -m pytest tests/ -v

# Frontend tests
cd frontend
npm install
npm test
```

## Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Verification

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0","mock_mode":false}

# List runs (requires auth token)
curl http://localhost:8000/api/runs \
  -H "Authorization: Bearer <your-jwt-token>"

# Submit a test ticket
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_source": "form",
    "form_data": {
      "title": "Add dark mode toggle",
      "description": "Allow users to switch between light and dark themes.",
      "acceptance_criteria": [
        {"given": "user is on dashboard", "when": "they click toggle", "then": "theme switches"}
      ],
      "priority": "medium",
      "components": ["frontend", "design-system"]
    }
  }'
```
