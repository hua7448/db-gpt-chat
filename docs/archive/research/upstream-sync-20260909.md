# Upstream Fix Sync: 2026-09-09

Target: `feature/k-ics-rebrand`, starting at `3d7d0060`.
Upstream baseline: `283128542b95f9e3c2773d3ef44eb4e12a66de81`.
Reviewed upstream head: `04559f9c`.

## Selected Commits

Applied with `git cherry-pick -x`, in this order:

| Upstream | Local | Change |
| --- | --- | --- |
| 165ddc27 | 01122a4b | Missing agent error module and agent regression tests |
| 338f71fa | 94467929 | SQLite file paths without a parent directory |
| 14a7edba | ce54727b | Return dictionary model-worker configuration |
| 3a8c60a2 | feb219e2 | Pass table name to Spark field lookup |
| 7c3cc2fd | 4f63edf5 | Reuse supplied embeddings in RAG evaluation example |

No source conflicts. The official agent error implementation replaces the
untracked local startup workaround and its tests. It has more specific error
categories; its TOOL_EXECUTION value is `tool_execution_error`.

## Validation

Used the existing UV-managed Python 3.11 environment, with PYTHONPATH pointing
to the isolated sync worktree. No dependency installation was needed.

- Agent error, parallel action, tool-calling agent, and SQLite tests:
  42 passed, 1 deselected.
- Deselected `test_query_ex`: already fails on both the original downstream
  and upstream head because `fetch="one"` returns `[(1,)]`, while the test
  expects `[1]`. This sync does not change that contract.
- Worker dictionary configuration: passed with a mocked configuration source.
- Spark summary argument forwarding: passed without a live Spark instance.
- Application router initialization, including `/api/v1/chat/react-agent`: passed.
- `git diff --check`: passed.

Full application startup, live database connections, live model calls, and the
RAG evaluation example with real embeddings were not run. The user's local
service remains stopped. Frontend, lockfile, package requirements, and database
migrations are unchanged; no frontend rebuild is needed.

## Deferred

- `7075e98c`: AWEL return fix still leaves a class-versus-instance check that
  rejects registered operator classes; needs a separate repair and tests.
- `f5f60151`: Synthorai provider is not needed by the DashScope deployment.
- `04559f9c`: upstream static assets conflict with K-ICS branding; excluded.

## Rollback

Revert the merge commit with `git revert -m 1 <merge-sha>` instead of rewriting
shared history. The official agent module would then be removed; restore the
backed-up local workaround before starting the pre-sync application again.
No database rollback or dependency changes are required.
