# Roadmap

Decisions and future plans from the kickoff discussion (2026-09-24).

## v1: MVP (built)
- [x] Python FastAPI backend with Claude tool-use agent loop
- [x] Google Places (New) Text Search, biased by GPS or the area named in the message
- [x] Memory: explicit profile, learned facts, location habits, 👍/👎 feedback
- [x] Android app (Expo): chat with place cards, location permission, settings
- [x] Server-held named LLM keys + per-client access codes (user, keys, allowed models, daily message/US$ limits), admin CLI (added 2026-09-24)
- [x] Settings: server URL + access code, model dropdown filtered by the code, optional own Claude key
- [ ] First real end-to-end run with a Places key + Claude key, then tune the system prompt

## Testing & CI (added 2026-09-26)
- [x] pytest suite for the backend (fakes for Claude + Places, temp DB per test), ruff lint/format
- [x] GitHub Actions: backend tests on Python 3.11 + 3.14, mobile `tsc` typecheck; `scripts/check.sh` runs the same locally
- [x] Rule in CLAUDE.md: every feature ships with tests, and CI stays green
- [x] Public repo at github.com/szeming23/palate; `main` protected (PR + green CI required, linear history), secret scanning, Dependabot (2026-09-26)
- [ ] Mobile unit tests (jest + React Native Testing Library) for the API client and settings
- [ ] Coverage report in CI (pytest-cov), with a minimum threshold

## v2: Telegram bot
- [ ] Bot using `python-telegram-bot`, calling the same `agent.chat()`, so there's no duplicated logic
- [ ] Handle Telegram location messages (📎 → Location) as lat/lng for the next query
- [ ] Render cards as messages with inline buttons (Open in Maps, 👍, 👎)
- [ ] `/login <access code>` in a private chat links a Telegram user id to an access code (store the link, not the code)
- [ ] Start with long polling on the dev PC; no public server needed

## Hosting (when it needs to run 24/7)
- [ ] Dockerfile for the backend
- [ ] Deploy to Fly.io or Railway (~$0–5/mo); alternatives are a Hetzner VPS (~€4/mo) or the Oracle Cloud free tier
- [ ] Move SQLite to a persistent volume, or to Postgres when multi-user
- [ ] HTTPS only; switch Telegram to webhooks if polling becomes a problem

## Multi-user
- [ ] Real auth (e.g. Supabase or Clerk) alongside or instead of access codes; `current_access()` in `main.py` is the single seam
- [ ] Per-user rate limits on Places calls (the Places key is shared and paid)
- [ ] Encrypt LLM keys at rest (currently plain env vars in `.env`) once the server is hosted
- [ ] Admin screen in the app (create/revoke codes, view usage) instead of CLI only
- [ ] Code expiry dates

## More LLM providers
- [ ] OpenAI and Gemini providers implementing `LLMProvider` (`backend/palate/llm/base.py`)
- [ ] Provider dropdown → model dropdown in Settings; one stored key per provider
- [ ] Streaming replies (show text as it arrives)

## Recommendation quality
- [ ] `get_place_details` tool (opening hours, reviews summary). Note that reviews use a pricier Places SKU
- [ ] Photos on cards (Places photo media, which is also billed separately)
- [ ] Cache Places results for a few hours to cut cost and latency
- [ ] "Visited" tracking plus a "surprise me with something new" mode that avoids repeats
- [ ] Memory hygiene: merge duplicate memories, and let the model update rather than only add/forget
- [ ] Better SG coverage for hawker stalls (maybe data.gov.sg hawker centre dataset as a supplement)
- [ ] Eval set of sample queries to check prompt changes don't regress picks

## App polish
- [ ] Feedback state persists when chat history reloads (currently only held in the card while open)
- [ ] Onboarding screen: key + preferences on first launch
- [ ] Map view of picks
- [ ] Production build (EAS) instead of Expo Go
