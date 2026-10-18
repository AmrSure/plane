# SGT Project Management Platform

Project and work tracking for Sure Global Tech teams: work items, cycles, modules, pages and analytics, self-hosted on our own infrastructure.

## Run it locally

You need Docker with Compose v2.

1. Create the env files from the examples and add secrets.

   ```bash
   cp .env.example .env
   cp apps/api/.env.example apps/api/.env
   echo "SECRET_KEY=\"$(tr -dc 'a-z0-9' < /dev/urandom | head -c50)\"" >> apps/api/.env
   ```

   For a single-host setup behind the bundled proxy, set these in `apps/api/.env`:
   `USE_MINIO=1`, `AWS_S3_ENDPOINT_URL="http://minio:9000"`, `CORS_ALLOWED_ORIGINS="http://localhost"`,
   and `http://localhost` for `WEB_URL` and every `*_BASE_URL`. Replace `LIVE_SERVER_SECRET_KEY` with a random value.

   Create `apps/live/.env` for the realtime server, using the same secret:

   ```bash
   PORT=3000
   API_BASE_URL="http://api:8000"
   WEB_BASE_URL="http://localhost"
   LIVE_BASE_URL="http://localhost"
   LIVE_BASE_PATH="/live"
   LIVE_SERVER_SECRET_KEY="<same value as in apps/api/.env>"
   REDIS_URL="redis://redis:6379/"
   ```

2. Build and start the stack.

   ```bash
   docker compose build
   docker compose up -d
   ```

3. Open http://localhost. The instance admin console is at http://localhost/god-mode.

### Demo data

To load demo users, a workspace, projects and work items:

```bash
docker compose exec -T api python manage.py shell < deployments/demo/seed_demo_data.py
```

## Branding

The product name, links, colors and logo come from `branding/brand.json`. The logo source is the official
vector in `branding/sgt/sure-logo.svg`.

| File | Purpose |
|---|---|
| `branding/brand.json` | Name, short name, slug, URLs, support email, colors |
| `branding/rebrand.py` | Applies the brand to the source: text, links, logo components, Docker names |
| `branding/patches.py` | Code changes: telemetry off, billing and upgrade prompts removed, support links |
| `branding/logo.py` | Logo variants built from the vector logo: full, wordmark, lockup, app icon |
| `branding/generate_assets.py` | Renders favicons, app icons, spinners and illustrations (needs Google Chrome) |
| `branding/applied.json` | The brand last applied, used to map old values on a rename |

To change the brand, edit `brand.json` and run:

```bash
python branding/rebrand.py
python branding/generate_assets.py
docker compose build && docker compose up -d
```

To move to a new upstream release, import its source, then run the same two scripts. A patch that no longer
matches the upstream code is reported as `PATCH FAILED` so it can be updated.

## Repository layout

| Path | Contents |
|---|---|
| `apps/api` | Django REST API, background workers and email templates |
| `apps/web` | Main web app |
| `apps/admin` | Instance admin console |
| `apps/space` | Public project pages |
| `apps/live` | Realtime collaboration server |
| `apps/proxy` | Caddy reverse proxy |
| `packages/*` | Shared UI, editor, i18n, types and utilities |
| `branding/` | Brand config and rebrand tooling |

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE.txt](LICENSE.txt) and [NOTICE.md](NOTICE.md).
