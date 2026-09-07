# Deployment runbook

Covers going from "runs locally via `docker-compose.yml`" to a real
pilot deployment via `docker-compose.prod.yml`. Read
[`ARCHITECTURE.md`](./ARCHITECTURE.md) first if you haven't already.

## Environments at a glance

| | `docker-compose.yml` | `docker-compose.prod.yml` |
|---|---|---|
| Purpose | Local development | Pilot / production |
| Postgres | Exposed on host `:5432` | Not exposed to host |
| Backend process | `uvicorn --reload`, 1 process | `gunicorn` + 4 uvicorn workers |
| Demo accounts | Auto-seeded (`SEED_ON_START=true`) | Never seeded — real accounts only |
| Frontend | Run separately via `npm run dev` | Built into a static nginx image |
| TLS | None (localhost) | Caddy, automatic via Let's Encrypt |
| Secrets | Hardcoded dev defaults | Required, validated at startup |

## Prerequisites

- A server (VM or bare metal) with Docker + Docker Compose v2 installed,
  ports 80 and 443 reachable from the internet.
- Two DNS records pointed at that server's IP — pick real subdomains,
  e.g.:
  - `app.yourdomain.gov.in` → the dashboard
  - `api.yourdomain.gov.in` → the backend API
  (Caddy needs these resolvable *before* first start to issue TLS certs.)

## First deploy

```bash
git clone <this-repo> && cd legal-metrology-checker

cp .env.prod.example .env.prod
# Edit .env.prod:
#   DOMAIN_APP, DOMAIN_API   — the two subdomains above
#   ACME_EMAIL                — ops contact for cert notices
#   JWT_SECRET_KEY             — openssl rand -hex 32
#   POSTGRES_PASSWORD          — openssl rand -hex 20

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

This builds and starts: `db` (Postgres, migrations run automatically on
backend startup via `entrypoint.sh`), `backend` (gunicorn), `frontend`
(nginx serving the built SPA), and `caddy` (reverse proxy + TLS).

**Create your first real admin account** — nothing is seeded in
production:

```bash
curl -X POST https://api.yourdomain.gov.in/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@yourdomain.gov.in","password":"<strong password>","full_name":"Your Name","role":"admin"}'
```

Then, as that admin, activate the rule config:

```bash
TOKEN=$(curl -s -X POST https://api.yourdomain.gov.in/auth/login \
  -d "username=you@yourdomain.gov.in&password=<strong password>" | jq -r .access_token)

curl -X POST https://api.yourdomain.gov.in/rule-versions/sync-from-file \
  -H "Authorization: Bearer $TOKEN"
```

Create additional inspector/supervisor accounts the same way (via
`/auth/register`, then have an admin adjust their role with
`PATCH /users/{id}` if they weren't registered with the right one).

## Secrets

| Variable | Where it's used | Rotation impact |
|---|---|---|
| `JWT_SECRET_KEY` | Signs/verifies every access token (`backend/app/auth.py`) | Rotating it invalidates every currently-issued token — everyone is logged out and must sign in again. Not catastrophic, but don't rotate casually mid-shift. |
| `POSTGRES_PASSWORD` | DB auth for the `metrology` user | Changing it requires updating both the `db` and `backend` service env in the same deploy — they'll disagree otherwise and the backend will fail to connect. |
| `ACME_EMAIL` | Let's Encrypt contact only | No functional impact if changed; purely for cert-expiry notices. |

None of these belong in the compose files themselves or in version
control — `.env.prod` is gitignored. If you're deploying via a CI/CD
pipeline instead of manually, use your platform's secrets manager
(GitHub Actions secrets, a cloud provider's secret store, etc.) to
populate `.env.prod` at deploy time rather than committing it anywhere.

## Backups

Postgres data lives in the `db_data` named volume. A minimal backup
approach for pilot scale:

```bash
# Backup
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  pg_dump -U metrology metrology | gzip > backup-$(date +%F).sql.gz

# Restore (into a fresh/empty DB)
gunzip -c backup-2026-09-06.sql.gz | \
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  psql -U metrology metrology
```

Run the backup command on a schedule (a cron job calling it nightly is
enough for a pilot) and copy the resulting file off the server —
a backup that lives on the same disk as the database it backs up
doesn't protect against disk failure.

Uploaded label images live in the `storage_data` named volume — back
this up too (`docker run --rm -v legal-metrology-checker_storage_data:/data -v $(pwd):/backup alpine tar czf /backup/storage-$(date +%F).tar.gz /data`)
if evidence photos need to survive a server loss, not just the DB
records referencing them.

## Rolling out a rule amendment without downtime

See [`RULES_CONFIG.md`](./RULES_CONFIG.md) for the full workflow. In
short: edit `rules/legal_metrology_rules.json` on the host (it's a
read-only bind mount, so no rebuild needed), then call
`POST /rule-versions/sync-from-file` as an admin. No restart, no
downtime — existing scans keep referencing their original `RuleVersion`.

## Updating the application itself

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Compose rebuilds only the images whose build context changed and
recreates those containers; `db`'s data volume is untouched.
Alembic migrations run automatically on backend container start — if a
migration is destructive or long-running, take a backup first (above)
and consider a maintenance window.

## Monitoring / logs

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f caddy
```

`GET /health` on the backend (unauthenticated) returns `{"status": "ok"}`
— point an uptime checker at `https://api.yourdomain.gov.in/health`.

For anything beyond a pilot's scale, this compose stack doesn't include
centralized log aggregation or metrics (Prometheus/Grafana, an ELK/Loki
stack, etc.) — add that once there's more than one server to reason
about.
