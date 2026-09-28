# Tasks

## 1. Relevance gate

- [x] 1.1 Add `typesafe_api_key` to `Settings` and `src/stolperfalle/relevance.py` (question, thresholds, model pin, one httpx call, band split, degraded on any failure); verify with `uv run pytest tests/test_relevance.py` covering ACT/CONFIRM/ASK split, nothing-applies, and a failing call degrading
- [x] 1.2 Wire the gate into `hook_query` only (shortlist 5, then trim to limit; `hints`; `degraded`); verify with `uv run pytest tests/test_hook_endpoints.py` including key-unset returning today's results with `degraded: true`
- [x] 1.3 Verify the `query` MCP tool is untouched and the full suite passes: `uv run pytest`
- [x] 1.4 Live check against the real store with the key set: `op run --env-file=~/dev/jev/.env.op -- uv run python -m` a one-off call of the gate on two fixture errors from `~/dev/jev/evals/fixtures/recall_errors.json`; verify the BusyBox grep error returns no results and the f-string error returns its KU (eval command: `uv run evals/stolperfalle_recall.py --eval` in the jev lab)

## 2. Rollout

- [ ] 2.1 Add `TYPESAFE_API_KEY` as a Komodo variable on the stolperfalle stack and deploy; verify a `/hook/query` call returns without `degraded`
- [ ] 2.2 Casey adds `modules/common/claude.sh` to zsh-setup and fast-forwards `~/.zsh-setup`; verify `type claude` shows the wrapper and a failing command in a new session gets either no hint or a relevant one
