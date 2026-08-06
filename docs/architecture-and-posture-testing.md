# utilitye2e-ai Architecture And Posture Testing

Last updated: 2026-08-06

## Purpose

`utilitye2e-ai` should not be treated as only a Playwright script generator. Its job is to support two separate test problems:

1. **Known-risk regression**
   - Behavior is already specified.
   - The tool discovers UI elements, generates executable steps, runs them, and reports DOM changes.
   - Output can become repeatable Playwright or runner-backed regression coverage.

2. **Unknown-risk posture review**
   - Behavior is not fully specified yet.
   - A reviewer walks role-based workflows and checks UX consistency, cross-screen logic, navigation posture, state clarity, and missing assertions.
   - Output becomes acceptance criteria, checklist items, or future automation.

Automation checks what somebody already knew to assert. Posture review is the mechanism for finding what the spec forgot to say.

## Architecture Direction

Keep the current repo architecture and extend it through clear boundaries:

```text
web / cli
  -> application workflows
    -> ai crawler/analyzer
    -> adapters
    -> core runner/auth/spec
  -> external posture packs
```

### Existing Boundaries

| Area | Responsibility | Rule |
|------|----------------|------|
| `core/` | Serializable contracts, browser auth, execution primitives | Keep public contracts backward compatible. |
| `application/` | Shared discover/analyze/run use cases | Web and CLI call this instead of duplicating orchestration. |
| `ai/` | Page crawling, inspection, prompts, LLM analysis | Expose reusable behavior through public boundaries. |
| `adapters/` | LLM and schema provider integrations | Keep config keys backward compatible. |
| `web/` | Flask routes, templates, static UI | Routes validate input, call workflows, and format responses. |
| `config/` | Declarative locator behavior | Prefer YAML locator strategies over hardcoded branches. |

### New Conceptual Boundary: Posture Packs

Posture packs are structured YAML inputs rendered into manual worksheets by the CLI. Public project planning and architecture notes live in repo `docs/`; small example packs live under repo `examples/` as executable sample inputs.

They define manual workflows and review prompts for a target product:

```text
posture-pack
  product
  roles
  workflows
  invariants
  cross-screen consistency checks
  evidence requirements
  bug-to-assertion mapping
```

Current command:

```bash
utilitye2e-ai posture render \
  --pack examples/classhub_posture_pack.yaml \
  --output /tmp/classhub-posture-worksheet.md
```

The renderer validates the pack and emits a checkbox-based release worksheet.

Manual findings can be recorded as structured YAML tied back to a workflow or check:

```bash
utilitye2e-ai posture finding create \
  --pack examples/classhub_posture_pack.yaml \
  --check-id parent-notification-date-consistency \
  --finding "Notification date and detail date disagree" \
  --impact "Parent cannot tell which contact-book item is current" \
  --missing-expectation "Same record should use one effective date across notification, list, and detail" \
  --suggested-assertion "Compare notification, list, and detail date for the same contact-book item" \
  --automation-candidate \
  --evidence screenshot-notification.png \
  --output /tmp/classhub-date-finding.yaml
```

Recorded findings can be listed from a file or folder:

```bash
utilitye2e-ai posture finding list --path /tmp/classhub-findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings --automation-candidates
utilitye2e-ai posture finding list --path /tmp/classhub-findings --format json
```

Automation-ready findings can be promoted into assertion candidate YAML:

```bash
utilitye2e-ai posture finding promote \
  --finding-file /tmp/classhub-date-finding.yaml \
  --priority high \
  --output /tmp/classhub-date-assertion.yaml
```

Promotion uses the finding's `suggested_assertion` first, then `missing_expectation`, then falls back to the finding text. Findings must be marked as automation candidates unless the reviewer passes `--force`.

## Testing Model

### Layer 1: Automated Regression

Use this when the expected behavior is already clear.

Examples:

- Button opens a modal.
- Login redirects to the dashboard.
- Creating a record adds a row.
- A saved item persists after reload.
- Notification endpoint returns the expected item.

`utilitye2e-ai` supports this through:

- page discovery,
- selected element analysis,
- `TestSpec`,
- `Runner`,
- locator strategies,
- DOM diff reporting.

### Layer 2: Posture Review

Use this when the risk is not explicitly captured by requirements.

Examples:

- An image viewer technically opens, but multi-image swipe is missing.
- Notification date and contact-book detail date use inconsistent logic.
- A user enters from a notification and the back path feels wrong.
- A page has an empty state but does not tell the user what to do next.
- Two roles see the same record with different wording or ordering.

These are not reliably discovered by generated scripts because the assertion does not exist yet.

### Layer 3: Assertion Harvesting

Every posture finding should be classified:

| Finding Type | Action |
|--------------|--------|
| Missing product expectation | Add acceptance criteria or checklist item. |
| Repeatable functional risk | Convert to automated assertion. |
| UX judgment | Keep in release smoke checklist. |
| Cross-screen consistency rule | Add invariant to posture pack and consider API/UI assertion. |
| Data/setup gap | Add seed or fixture requirement. |

This creates the loop:

```text
manual posture finding
  -> product expectation
  -> assertion
  -> automation when stable
```

## Scenario Pack Direction

Scenario packs should be modular and product-aware without copying product implementation.

Current executable sample:

```text
examples/classhub_posture_pack.yaml
```

Recommended future shape:

```text
scenario-packs/
  classhub/
    roles.yaml
    workflows.yaml
    invariants.yaml
    smoke-checklist.md
  generic-saas/
    auth.yaml
    navigation.yaml
    crud.yaml
```

Do not duplicate a product's auth flow. Product repos should expose login helpers, seeded users, token setup, or test endpoints. `utilitye2e-ai` should call those boundaries through adapters or runtime configuration.

## MVP Roadmap

### Done

- README describes the dual testing posture.
- Public project planning lives under repo `docs/`.
- ClassHub has the first concrete posture checklist.
- `core.posture` defines the structured posture pack contract.
- `application.render_posture_pack()` renders packs through the shared workflow layer.
- `utilitye2e-ai posture render` produces a manual worksheet.
- `core.posture.PostureFinding` defines the structured finding record.
- `application.create_posture_finding_record()` validates findings through the shared workflow layer.
- `utilitye2e-ai posture finding create` records manual findings as YAML.
- `application.list_posture_finding_records()` loads finding files/folders through the shared workflow layer.
- `utilitye2e-ai posture finding list` summarizes findings as table, JSON, or YAML.
- `core.posture.PostureAssertionCandidate` defines the promotion target for automation-ready findings.
- `application.promote_posture_finding_record()` promotes a finding through the shared workflow layer.
- `utilitye2e-ai posture finding promote` emits assertion candidate YAML.

### Now

- Use the ClassHub example pack before release.
- Classify manual findings through the bug-to-assertion template.
- Decide which ClassHub findings should become automated assertions.

### Next

- Add optional JSON output for CI/report integration.
- Add report fields for "manual finding", "converted assertion", and "automation candidate".
- Add assertion candidate listing and status tracking.
- Add a first assertion-to-TestSpec scaffold for UI checks.

### Later

- Generate suggested assertions from posture findings.
- Attach screenshots, traces, and DOM snapshots as evidence.
- Track posture coverage by role and workflow.
- Support product-specific adapters for fixture setup and cleanup.

## Design Guardrails

- Do not create duplicated auth flow.
- Do not put crawler, runner, adapter construction, or auth logic directly in Flask routes.
- Do not make unknown-risk review pretend to be deterministic automation.
- Do not make product-specific rules global defaults.
- Keep `core.spec` backward compatible.
- Keep posture review output separate from generated executable specs until the assertion is clear.
