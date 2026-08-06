# ClassHub Posture Smoke Checklist

Last updated: 2026-08-06

## Purpose

This checklist covers the ClassHub risks that normal automated E2E scripts can miss because the assertion was never written. It complements regression tests; it does not replace them.

Run it before release when a workflow touches parent, teacher, notification, contact-book, image, or cross-screen data display behavior.

Structured pack source:

```text
examples/classhub_posture_pack.yaml
```

Render command:

```bash
utilitye2e-ai posture render \
  --pack examples/classhub_posture_pack.yaml \
  --output /tmp/classhub-posture-worksheet.md
```

Finding command:

```bash
utilitye2e-ai posture finding create \
  --pack examples/classhub_posture_pack.yaml \
  --check-id parent-image-multiple-browse \
  --finding "Image opens but cannot browse multiple attachments" \
  --impact "Parent cannot inspect every image from the detail view" \
  --output /tmp/classhub-image-finding.yaml
```

Finding list command:

```bash
utilitye2e-ai posture finding list --path /tmp/classhub-findings
utilitye2e-ai posture finding list --path /tmp/classhub-findings --automation-candidates
```

Promote automation-ready finding:

```bash
utilitye2e-ai posture finding promote \
  --finding-file /tmp/classhub-findings/image.yaml \
  --priority high \
  --output /tmp/classhub-findings/image-assertion.yaml
```

## Review Rules

- Test as a real role, not only as an admin.
- Start from the user's natural entry point, such as a notification, not only from the main menu.
- Compare list, detail, notification, and attachment behavior for the same record.
- Record every issue as one of:
  - missing acceptance criteria,
  - automation candidate,
  - UX checklist item,
  - data/setup gap.

## Parent Workflow

### Notification To Contact Book

- Parent receives a contact-book notification.
- Notification opens the expected contact-book detail.
- Notification title, preview text, and detail title refer to the same item.
- Notification date and contact-book date use the same business logic.
- Returning from detail lands somewhere reasonable for the parent workflow.
- Read/unread or badge state updates consistently after opening.
- Missing or expired content has a clear state instead of a broken page.

### Contact Book List And Detail

- List ordering matches the expected date logic.
- Detail date, list date, and notification date are consistent.
- Empty list state explains the situation without sounding like an error.
- Loading state does not hide stale content as if it were current content.
- Error state offers a recoverable action when possible.
- Detail content does not require teacher/admin vocabulary to understand.

### Image Attachments

- Single image opens, closes, and preserves context.
- Multiple images support next/previous browsing or another explicit gallery affordance.
- Swipe, arrow, or thumbnail behavior matches the device expectation.
- Zoomed image can be dismissed without losing the workflow.
- Image viewer does not trap scroll or browser back unexpectedly.
- Broken image has a visible fallback state.

### Parent Reply

- Reply entry point is visible when replies are allowed.
- Reply disabled state explains why it is disabled.
- Sending a reply updates parent detail state.
- Teacher/admin side can see the reply with matching timestamp and student context.
- Duplicate submit is prevented or handled cleanly.

## Teacher Workflow

### Publish Contact Book

- Teacher creates or edits a contact-book item.
- Required fields are obvious before submission.
- Attached images appear in preview before publish.
- Published item appears in the teacher list with the same title/date as parent side.
- Parent notification appears for the intended audience only.
- Draft, scheduled, and published states are visually distinct if supported.

### Review Parent Side Result

- After publishing, switch to parent role and open from notification.
- Confirm content, date, image, and reply behavior match the teacher intent.
- Confirm students outside the target group do not see the item.

## Admin Workflow

### Identity And Data Consistency

- Student, parent, class, and teacher relationship changes appear consistently across role views.
- Parent display names and student labels do not conflict across list/detail/notification.
- Deleted or inactive records do not appear as actionable content.
- Tenant or class context is not leaked across accounts.

## Cross-Screen Invariants

Use these as product-level expectations. If one breaks, decide whether it should become an automated assertion.

| Invariant | Review Question |
|-----------|-----------------|
| Same record, same date logic | Does the same item show the same effective date across notification, list, and detail? |
| Same record, same audience | Do all intended recipients see it, and only them? |
| Same attachment, same viewer behavior | Does image behavior stay consistent across entry points? |
| Role-specific language | Does the text match the user's role and vocabulary? |
| Recoverable state | Can the user recover from loading, empty, expired, or failed states? |
| Back path sanity | Does browser/app back return to a useful place? |

## Bug To Assertion Mapping

Use this after every manual finding.

```text
Finding:
User impact:
Missing expectation:
Should become automated? yes/no
Suggested assertion:
Suggested checklist update:
Evidence:
Owner:
```

## Current Known Findings To Preserve

| Finding | Classification | Future Coverage |
|---------|----------------|-----------------|
| Image can enlarge but cannot browse multiple images by swipe/next/previous | Missing UX expectation | Add gallery behavior to checklist; automate only after product decision. |
| Notification and contact-book date logic can diverge | Cross-screen consistency risk | Add invariant assertion comparing notification/list/detail for the same item. |

## Release Gate

Before release, complete at least:

- Automated known-risk suite passes.
- Parent notification-to-contact-book path checked manually.
- Teacher publish-to-parent-view path checked manually.
- Image attachment behavior checked with one image and multiple images.
- At least one cross-role consistency pass for date, audience, and content.
- New findings classified and either converted to assertions or retained in this checklist.
