# Palate: notes for Claude

Singapore food-recommendation agent. FastAPI backend (`backend/palate/`) holds all logic; the Expo app (`mobile/`) and the future Telegram bot are thin clients. See README.md for architecture and TODO.md for the roadmap.

The public README is a project showcase for visitors: no setup steps, account or key instructions. Setup and operations notes (Google Places and Claude keys, access codes, running the backend and app, SonarCloud and branch-protection settings) live in the private repo `szeming23/palate-ops`, cloned next to this one at `../palate-ops`. Update that repo when setup steps change.

## Testing rules (required)

The test suite is the regression net. CI (`.github/workflows/ci.yml`) runs it on every push and PR, and it must stay green.

1. **Every feature or bug fix comes with tests in the same change.** New behaviour gets new tests. A bug fix gets a test that fails without the fix.
2. **Run `./scripts/check.sh` before saying work is done.** It runs the same steps as CI: ruff lint + format check, pytest, the mobile typecheck and jest tests. If anything fails, fix it or tell the user it's failing. Don't call the work finished while it's red.
3. **Don't weaken existing tests to make a change pass.** If a test fails, assume the change broke something. Only edit or delete a test when the behaviour it checks was changed on purpose, and say so to the user.
4. **Tests never hit real services or real data.** `backend/tests/conftest.py` gives every test a temp SQLite DB and fake keys, and has fakes for Claude (`provider` fixture, `ScriptedProvider`) and Google Places (`fake_places`). Use them. No real API keys, no network, no `palate.db`.
5. When adding an LLM provider, a tool, an endpoint or a DB table, follow the matching test file:

| Code | Tests |
|---|---|
| `access.py` (codes, limits, key choice) | `tests/test_access.py` |
| `agent.py` (context, one chat turn) | `tests/test_agent.py` |
| `main.py` (HTTP routes, auth, error codes) | `tests/test_api.py` |
| `tools.py` | `tests/test_tools.py` |
| `places.py` (Google request/parse) | `tests/test_places.py` |
| `db.py` | `tests/test_db.py` |
| `llm/anthropic_provider.py` | `tests/test_anthropic_provider.py` (fake Anthropic client) |
| `admin.py` | `tests/test_admin.py` |
| `config.py` | `tests/test_config.py` |

Some tests guard important rules. Keep them passing:
- Cards are built only from places the search returned, so the model can't invent a restaurant (`test_present_only_builds_cards_from_searched_places`).
- A friend's access code can't read or change another user's data (`test_users_are_isolated`).
- Using the client's own key skips the US$ budget but not the message cap.
- The Places field mask stays on the cheaper SKU (`test_field_mask_stays_on_the_cheap_sku`).

The mobile app uses jest (`jest-expo` preset) with React Native Testing Library, in `mobile/__tests__/`, plus `tsc` via `npm run typecheck`. Keep both passing. Mock the backend with `jest.mock("../lib/api")` and device storage with `test-utils/secureStoreMock.ts`; tests never call a real server.

| Code | Tests |
|---|---|
| `mobile/lib/api.ts` | `__tests__/api.test.ts` (fake `fetch`) |
| `mobile/lib/settings.ts` | `__tests__/settings.test.ts` |
| `mobile/components/PlaceCard.tsx` | `__tests__/PlaceCard.test.tsx` |
| `mobile/app/index.tsx` (chat) | `__tests__/ChatScreen.test.tsx` |
| `mobile/app/settings.tsx` | `__tests__/SettingsScreen.test.tsx` |

## Git workflow

The repo is public at https://github.com/szeming23/palate, and `main` is protected, even for the owner:
- No direct pushes to `main`. Changes go in through a PR with a linear history (squash merge only).
- The `backend (3.11)`, `backend (3.14)`, `mobile` and `sonarcloud` CI checks must pass. `sonarcloud` fails when the SonarCloud quality gate fails (no new bugs, vulnerabilities or unreviewed hotspots, and at least 80% coverage on new code). It skips the scan on Dependabot PRs, which have no `SONAR_TOKEN`. The branch must also be up to date with `main`.
- Every review conversation must be resolved. Force pushes and deleting `main` are blocked.
- Secret scanning with push protection is on. Still, never commit `.env`, keys or `palate.db`.

The flow: make a branch (`feat/...`, `fix/...`, `ci/...`), commit, run `./scripts/check.sh`, push, then `gh pr create`. Wait for CI with `gh pr checks --watch`, then merge with `gh pr merge --squash`. Only commit, push or merge when the user asks.

Dependabot opens weekly PRs for GitHub Actions and pip, plus security PRs. Merge them only when CI is green. Expo packages aren't in Dependabot; upgrade them with `npx expo install --fix`.

## Commands

```bash
./scripts/check.sh                                  # everything CI runs
cd backend && .venv/bin/pytest -q                   # backend tests only
cd backend && .venv/bin/ruff check --fix . && .venv/bin/ruff format .   # auto-fix lint/format
cd backend && .venv/bin/pip install -e '.[dev]'     # install test/lint tools
cd mobile && npm test                               # mobile tests only (add -- --coverage for a report)
```

## Conventions

- Put new features in the shared backend, not in one client.
- Keep `user_id` on every table (multi-user is planned).
- Update TODO.md when plans change or items get done.
