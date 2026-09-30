# Palate 🍜

[![CI](https://github.com/szeming23/palate/actions/workflows/ci.yml/badge.svg)](https://github.com/szeming23/palate/actions/workflows/ci.yml)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=szeming23_palate&metric=alert_status)](https://sonarcloud.io/project/overview?id=szeming23_palate)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=szeming23_palate&metric=coverage)](https://sonarcloud.io/project/overview?id=szeming23_palate)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=szeming23_palate&metric=bugs)](https://sonarcloud.io/project/overview?id=szeming23_palate)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=szeming23_palate&metric=vulnerabilities)](https://sonarcloud.io/project/overview?id=szeming23_palate)

A food buddy that remembers you. Tell it what you feel like ("bishan chicken rice", "cheap dinner near me") and it searches real places nearby, then recommends a few picks based on your tastes, dietary needs, past 👍/👎 and where you usually hang out.

## Architecture

```
 Android app (Expo) ──┐
                      ├──► Palate backend (FastAPI, Python) ──► LLM (Claude, server-held or user's own key)
 Telegram bot (later) ┘        │   agent loop + tools          ──► Google Places API (server-held key)
                               └── SQLite (memory, history, feedback)
```

- **The backend holds all the logic** (agent loop, memory, tools), so the app and the future Telegram bot stay thin and behave the same.
- **LLM keys live on the server, unlocked by access codes.** The server holds any number of named keys. Each client (a phone, a dev laptop, a friend, later the Telegram bot) gets its own **access code**, which maps to:
  - a user (whose memory and history it uses)
  - which named key(s) to bill
  - which models it may use
  - daily limits: a message count and/or a US$ budget

  Codes are random (`plt_...`) and stored only as SHA-256 hashes. Revoking one locks out that client without touching the underlying key.
- **Optional own key.** A client can still enter its own Claude key in Settings. It's stored encrypted on the phone and sent as `X-LLM-API-Key` for that request only (never saved on the server), and it skips the code's US$ budget.
- **The Google Places key stays on the server.** Anything bundled in an APK can be extracted, so no key ever ships in the app.
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

## Engineering

- **CI on every push and PR** (GitHub Actions): ruff lint + format check, the backend test suite on Python 3.11 and 3.14, TypeScript typecheck, and the mobile test suite.
- **Automated tests that need no keys or network:** pytest for the backend (temp database per test, fake Claude and Google Places clients) and jest + React Native Testing Library for the app (mocked server and device storage).
- **Static analysis and coverage** with [SonarQube Cloud](https://sonarcloud.io/project/overview?id=szeming23_palate): bugs, vulnerabilities, security hotspots, code smells, duplication and coverage from both test suites. The quality gate is a required check, so a PR that adds a bug, a vulnerability or untested code can't merge.
- **Protected `main`:** changes land only through PRs with all checks green and a linear history. Secret scanning with push protection is on, and Dependabot sends weekly dependency updates that go through the same checks.

Run everything CI runs, locally: `./scripts/check.sh`. Contributor and testing rules are in [CLAUDE.md](CLAUDE.md).

## Project layout

```
backend/palate/
  main.py         HTTP routes
  agent.py        system prompt, context building, one chat turn
  tools.py        tool definitions + execution
  places.py       Google Places API (New) client
  db.py           SQLite schema + queries
  access.py       access codes: key selection, allowed models, daily limits
  admin.py        CLI to manage access codes
  config.py       env config, including named LLM keys
  llm/            provider interface + Claude implementation + model list
backend/tests/    pytest suite (conftest.py has the fakes)
mobile/
  app/index.tsx     chat screen
  app/settings.tsx  connection + access code, model dropdown, optional own key, preferences, memories
  components/PlaceCard.tsx
  lib/              API client, secure settings, theme
  __tests__/        jest tests (test-utils/ has the SecureStore fake)
```

See [TODO.md](TODO.md) for the roadmap.
