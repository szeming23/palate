# Palate 🍜

A food buddy that remembers you. Tell it what you feel like ("bishan chicken rice", "cheap dinner near me") and it searches real places nearby, then recommends a few picks based on your tastes, dietary needs, past 👍/👎 and where you usually hang out.

## Architecture

```
 Android app (Expo) ──┐
                      ├──► Palate backend (FastAPI, Python) ──► LLM (Claude, via the user's own API key)
 Telegram bot (later) ┘        │   agent loop + tools          ──► Google Places API (server-held key)
                               └── SQLite (memory, history, feedback)
```

- **The backend holds all the logic** (agent loop, memory, tools), so the app and the future Telegram bot stay thin and behave the same.
- **LLM keys live on the server, unlocked by access codes.** `backend/.env` holds any number of named keys (e.g. `anthropic-main`, `anthropic-dev`). Each client (your phone, your dev laptop, a friend, later the Telegram bot) gets its own **access code**, which maps to:
  - a user (whose memory and history it uses)
  - which named key(s) to bill
  - which models it may use
  - daily limits: a message count and/or a US$ budget

  Codes are random (`plt_...`) and stored only as SHA-256 hashes. Revoking one locks out that client without touching your Claude key. See [Access codes](#access-codes).
- **Optional own key.** A client can still enter its own Claude key in Settings. It's stored encrypted on the phone and sent as `X-LLM-API-Key` for that request only (never saved on the server), and it skips the code's US$ budget.
- **The Google Places key stays on the server** (`backend/.env`). Anything bundled in an APK can be extracted, so it must never go in the app.
- **One user for now**, but every table has a `user_id` column so multi-user is an auth change, not a rewrite.
- **Providers are pluggable**: `backend/palate/llm/` has a `LLMProvider` interface. Claude is the only provider so far.

### How a chat turn works

1. The app sends the message, the chosen model and (optionally) GPS coordinates.
2. The backend builds a system prompt with your profile, remembered facts/locations, recent 👍/👎 and the current SG time.
3. The model calls tools:
   - `search_places`: Google Places Text Search, biased to your location if you didn't name an area
   - `save_memory` / `forget_memory`: learns lasting facts ("dislikes coriander", "works near Raffles Place")
   - `present_recommendations`: 3–5 picks with reasons. Cards are built **only** from places the search actually returned, so the model can't invent a restaurant.
4. The app shows the reply plus place cards (rating, price, distance, open now, Maps link, 👍/👎).

### Memory

| Kind | Where it comes from | Stored in |
|---|---|---|
| Explicit preferences (diet, allergies, budget, likes/dislikes) | Settings screen | `profiles` |
| Learned facts | The model saves them from chat | `memories` (kind `fact`) |
| Location habits | The model saves them from chat | `memories` (kind `location`) |
| History & feedback | Each recommendation + your 👍/👎 | `recommendations`, `messages` |

You can view and delete learned memories in Settings.

## Setup

### 1. Google Places API key

1. Create a Google Cloud account at https://console.cloud.google.com and a project (e.g. `palate`). Billing must be enabled, even for free usage.
2. **APIs & Services → Library → "Places API (New)" → Enable.**
3. **APIs & Services → Credentials → Create credentials → API key.** Edit the key:
   - *API restrictions* → restrict to **Places API (New)** only.
4. **Protect your wallet:**
   - **Billing → Budgets & alerts**: create a budget (e.g. US$5) with email alerts.
   - **APIs & Services → Places API (New) → Quotas**: lower the per-day request cap (e.g. 200/day). This is the only *hard* stop; budgets only send alerts.
5. Pricing: Google gives a free monthly usage allowance per SKU. We request rating/price/opening-hours fields, which fall under a higher Text Search tier, so check the current numbers on the [pricing page](https://developers.google.com/maps/billing-and-pricing/pricing). Personal use should stay well within the free allowance.

### 2. Backend

WSL/Ubuntu needs `venv` support first:

```bash
sudo apt install python3-venv python3-pip      # or install uv: curl -LsSf https://astral.sh/uv/install.sh | sh
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env                            # fill in GOOGLE_PLACES_API_KEY and PALATE_KEY_* lines
python -m palate.admin keys                     # check your keys loaded
python -m palate.admin codes add my-phone --key anthropic-main --daily-usd 3   # prints your access code
uvicorn palate.main:app --host 0.0.0.0 --port 8000 --reload
```

Check it: `curl localhost:8000/health`. API docs are at http://localhost:8000/docs.

### 3. Android app

Install Node.js (LTS) in WSL, e.g. via [nvm](https://github.com/nvm-sh/nvm): `nvm install --lts`.

```bash
cd mobile
npm install expo@latest
npx expo install expo-router react react-native react-native-screens react-native-safe-area-context \
  expo-linking expo-constants expo-status-bar expo-location expo-secure-store @react-native-picker/picker
npx expo install -- --save-dev typescript @types/react
npx expo start --tunnel
```

Install **Expo Go** from the Play Store and scan the QR code.

In the app, open **Settings** and fill in:
- **Palate server URL**: see below
- **Access code**: the `plt_...` code printed by `codes add`
- Tap **Connect**, then pick a **Model** (the list shows only what your code allows)

#### Letting your phone reach the backend inside WSL

WSL2 sits behind NAT, so the phone can't see `localhost:8000` directly. Pick one of these:

- **Easiest: a tunnel.** Run `cloudflared tunnel --url http://localhost:8000` (no account needed) and paste the `https://….trycloudflare.com` URL into Settings. This also works when you're away from home Wi-Fi.
- **Same Wi-Fi.** On Windows 11, add `[wsl2]` / `networkingMode=mirrored` to `%UserProfile%\.wslconfig`, run `wsl --shutdown`, allow port 8000 in Windows Firewall, then use `http://<your-PC's-LAN-IP>:8000`.

## Access codes

Keys go in `backend/.env` as `PALATE_KEY_<NAME>=<provider>:<secret>`:

```
PALATE_KEY_ANTHROPIC_MAIN=anthropic:sk-ant-...     → "anthropic-main"
PALATE_KEY_ANTHROPIC_DEV=anthropic:sk-ant-...      → "anthropic-dev"
```

Manage codes with the admin CLI (run inside `backend/` with the venv active):

```bash
python -m palate.admin keys                                    # list configured keys (masked)
python -m palate.admin codes add my-phone --key anthropic-main --daily-usd 3
python -m palate.admin codes add dev-laptop --key anthropic-dev
python -m palate.admin codes add friend --user friend --key anthropic-main \
    --models claude-haiku-4-5 --daily-messages 50
python -m palate.admin codes list                              # codes + today's usage
python -m palate.admin codes remove friend                     # revoke immediately
```

- `--user` decides whose memory and history the code shares. Your phone and laptop both default to `me`; give a friend their own user so your memories stay separate.
- A code can list one `--key` per provider (e.g. an Anthropic key and, later, an OpenAI key).
- The US$ budget is estimated from token usage and model prices in `backend/palate/llm/__init__.py`. It's checked *before* each message, so the last message of the day can go slightly over. Set a spending limit in the Anthropic Console too, as a hard backstop.
- Limits reset at midnight Singapore time.

## Tests & CI

```bash
cd backend && pip install -e '.[dev]'   # once
./scripts/check.sh                      # lint + backend tests + mobile typecheck (same as CI)
```

GitHub Actions (`.github/workflows/ci.yml`) runs the same checks on every push and PR. Tests use a temp database and fake Claude/Places clients, so they need no keys and cost nothing. Every feature should add tests; see [CLAUDE.md](CLAUDE.md).

CI also measures backend test coverage (pytest-cov) and sends it, with the code, to [SonarCloud](https://sonarcloud.io/project/overview?id=szeming23_palate) for static analysis: bugs, security hotspots, code smells and duplication. Settings live in `sonar-project.properties`; the scan needs the `SONAR_TOKEN` repo secret and is skipped on Dependabot PRs, which can't read it.

## Project layout

```
backend/palate/
  main.py         HTTP routes
  agent.py        system prompt, context building, one chat turn
  tools.py        tool definitions + execution
  places.py       Google Places API (New) client
  db.py           SQLite schema + queries
  access.py       access codes: key selection, allowed models, daily limits
  admin.py        CLI to manage access codes (`python -m palate.admin`)
  config.py       env config, including named LLM keys
  llm/            provider interface + Claude implementation + model list
backend/tests/    pytest suite (conftest.py has the fakes)
mobile/
  app/index.tsx     chat screen
  app/settings.tsx  connection + access code, model dropdown, optional own key, preferences, memories
  components/PlaceCard.tsx
  lib/              API client, secure settings, theme
```

See [TODO.md](TODO.md) for the roadmap.
