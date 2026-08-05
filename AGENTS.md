# AGENTS.md - utilitye2e-ai

## Core Rules

- Always preserve the existing project architecture and public contracts.
- Prefer minimal diffs scoped to the requested behavior.
- Follow the existing folder structure. Add new folders only when they clarify an architectural boundary.
- Do not remove backward compatibility unless explicitly requested.
- Update tests when behavior changes or when moving behavior across layers.
- Run the formatter after editing Python code. Prefer formatting only the files you touched.
- Run the relevant tests before finishing. Use `pytest -q` for normal changes.
- If a database migration is needed, generate the migration instead of applying schema changes ad hoc.

## Architecture Boundaries

- `core/` contains domain contracts and execution primitives.
  - Keep `core.spec` as the serializable test contract.
  - Keep browser authentication behind `core.auth`; do not create another auth flow.
  - Keep runner behavior in `core.runner`; do not move HTTP or UI concerns into `core`.
- `application/` contains use-case workflows shared by CLI and web.
  - Put orchestration such as discover, analyze, and run workflows here.
  - CLI and web should call this layer instead of duplicating orchestration.
- `ai/` contains AI-assisted browser inspection, crawling, prompts, and LLM-facing analysis.
  - Do not make web routes depend on private functions in this package.
  - If a private helper must be reused elsewhere, expose it through an appropriate public boundary first.
- `adapters/` contains replaceable integrations such as LLM and schema providers.
  - Keep adapter factories backward compatible with existing config keys.
- `web/` contains Flask routes, templates, and static UI.
  - Keep Flask routes thin: validate request data, call application workflows, and format responses.
  - Do not place crawler, runner, adapter construction, or auth logic directly in routes.
- `config/` contains declarative runtime behavior such as locator strategies.
  - Prefer config-driven locator changes over hardcoded selector branches.

## Authentication

- Never create duplicated auth flow.
- Use `core.auth.login_page()` for browser login in execution paths.
- Use `core.auth.resolve_login_url()` when resolving relative login paths for `TargetSpec`.
- If crawler login behavior needs to change, keep one canonical implementation and route callers through the public auth boundary.

## Tests And Validation

- Add focused unit tests for pure application/core behavior.
- Avoid requiring Playwright, real browsers, real LLM calls, or real databases in unit tests unless the requested change specifically targets those paths.
- For architecture refactors, cover:
  - shared workflow behavior,
  - serialization/backward compatibility,
  - auth URL resolution,
  - route/CLI contract preservation when practical.

## Git Hygiene

- The worktree may contain user changes. Do not revert changes you did not make unless the user explicitly asks.
- Before committing, inspect `git status --short`.
- Keep generated caches, screenshots, and virtualenv files out of commits.
- If a formatter touches unrelated files, restore the formatter-only noise before committing when possible.

## Documentation Storage Policy

All repo should not store any doc on repo `docs` folder. All repo doc should move to `/home/apollo/Project_detail/{project name}` folder, because some repo may be public and no doc should be released to others by accident.

When creating or updating project documentation, write it under `/home/apollo/Project_detail/{project name}/` and link to it from the repo only when a pointer is necessary. Do not create or repopulate a tracked `docs/` directory in the repo.
