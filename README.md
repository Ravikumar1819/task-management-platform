# Task Management Platform

React task board with a Flask REST API, JWT authentication and project-level ownership.

This is a fresh implementation based on the project description in Ravi Kumar's resume. It does not claim to recover an earlier codebase or demonstrate past production usage.

## Run locally

Requires Python 3.11+. From this repository:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m flask --app app run --port 5000
```

Open http://localhost:5000. Set configuration as environment variables; `.env.example` documents the available values. Flask does not automatically load `.env` unless python-dotenv is installed. For persistent sessions set SECRET_KEY to a random secret. SQLite data is created automatically in `instance/app.db`. To reset local data, stop the server and remove that database.

## Verify

```sh
python -m pytest -q
python -m ruff check .
```

## Docker

```sh
docker build -t task-management-platform .
docker run --rm -p 5000:5000 -e SECRET_KEY=your-random-secret -v task-management-platform-data:/app/instance task-management-platform
```

The image serves with Waitress as a non-root user. Check volume ownership if using a host directory. `/api/health` returns a health check. Never commit `.env`, database files or credentials.

## Deployment boundaries

This is a portfolio application. Before public deployment, use HTTPS, set COOKIE_SECURE=true for cookie apps, configure a persistent database and SECRET_KEY, add authentication rate limiting, monitoring and backups, and review access rules. No default account or password is shipped. CI is configured to run lint and tests on pushes and pull requests.

## React frontend setup

Requires Node 22+. Before starting Flask, build the UI:

```sh
cd frontend
npm ci
npm run build
cd ..
python -m flask --app app run --port 5000
```

For frontend hot reload, run Flask on port 5000 and `npm run dev` in frontend in a second terminal. Vite proxies /api to Flask. No CORS wildcard is needed. Docker builds the UI in a separate Node stage.

## Authentication and API

Self-register, sign in and create a project. Users own projects; tasks inherit that ownership. Every read/write checks ownership, including task moves and deletion. Passwords are hashed with scrypt. JWTs expire after one hour, require an issuer and standard claims, and use an explicit HS256 allowlist. Tokens stay in React memory and are cleared on page reload or sign-out. Sign-out clears the client token; server-side token revocation is not implemented. Use a strong persistent SECRET_KEY in deployment.

POST /api/register and /api/login accept username/password JSON. Login returns token, username and expires_in. Other endpoints require Authorization: Bearer <token>. GET/POST /api/projects; PUT/DELETE /api/projects/id; GET /api/tasks?project_id=id&page=1&limit=20; POST /api/tasks with project_id,title,status; PUT /api/tasks/id with title,status; DELETE /api/tasks/id. Status is todo, doing or done. Errors use an `error` field. The board paginates all tasks together and explains that its columns show the current page.
