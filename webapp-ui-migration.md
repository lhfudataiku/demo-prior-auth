# Webapp UI Migration Status

## Purpose

This document captures the implemented UI migration work for the prior-auth
webapp, the remaining gaps, and the current validation status. It started as a
plan and now serves as the rollout record for the redesigned local branch.

## Current Implementation Status

Implemented on the current local branch:

- Validation scope
  - all work below has been implemented and checked locally only
  - current verification has been limited to `npm run type-check`,
    `npm run build`, and local fixture-backed/manual UI flows
  - no DSS-hosted validation has been completed yet
  - streaming and HITL presentation in `dss` mode should still be treated as
    pending live-environment review

- Phase 1 foundation started
  - Tailwind v4 and the Vite Tailwind plugin added
  - Dataiku-aligned token file added at
    `webapps/prior_auth_review/src/styles/tokens.css`
  - `src/style.css` updated to bridge semantic tokens into utility classes
- Phase 2 primitive layer started
  - local UI primitives added under
    `webapps/prior_auth_review/src/components/ui/`
- Phase 3 shell migration started
  - `webapps/prior_auth_review/src/App.vue` migrated to the new utility-based
    shell
- Phase 4 shared sidebar card migration started
  - patient summary, scope summary, reviewer note card, and workflow nav
    migrated to the new design system
- Phase 5 Screen 1 migration started
  - Screen 1 layout updated to use the new shell primitives and tokenized form
    styling
- Phase 6 Screen 2 migration completed
  - Screen 2 progress, summary tiles, and criterion review cards migrated to
    the new tokenized component layer
- Phase 7 Screen 3 migration completed
  - Screen 3 outcome and deterministic summary views migrated to the new
    tokenized component layer
  - Screen 3 summary logic was simplified from mixed
    `answered/unanswered/warnings` groupings into deterministic
    `satisfied/rejected/unresolved` criterion buckets
  - clinician/chart disagreement now renders as card-level audit metadata
    rather than a duplicate criterion section
  - `submission_ready` now follows cluster satisfaction instead of merely
    absence of unresolved items

Still pending:

- broader legacy CSS cleanup after the remaining screens are migrated
- DSS-hosted visual/behavioral verification of the streaming Screen 2
  experience
- possible follow-up cleanup of lightweight/legacy summary components that are
  no longer used by the main flow

The target is to align the webapp with the company blueprint and Dataiku brand
template represented by:

- `/Users/li-hengfu/Documents/GitHub/bs-blueprint`
- `/Users/li-hengfu/.agents/skills/dataiku-internal-branding/SKILL.md`
- `/Users/li-hengfu/.agents/skills/dataiku-internal-branding/references/styling.md`

This is primarily a frontend redesign and component-system alignment effort. It
was intended to avoid contract changes, but the implemented work did introduce
small deterministic Screen 3 payload changes to remove duplicated criterion
cards and align the audited summary with final criterion outcomes.

This work should not change:

- the Screen 1 / Screen 2 / Screen 3 workflow contract
- the `local` vs `dss` runtime split
- the Screen 2 Structured Agent / Screen 3 deterministic ownership boundary
- the Pinia store behavior unless needed for UI wiring only
- the Screen 2 Structured Agent execution boundary

Implemented exception:

- Screen 3 deterministic payload shape now uses:
  - `satisfied_criteria`
  - `rejected_criteria`
  - `unresolved_criteria`
  - `review_alerts`
  instead of the older mixed `answered_criteria`,
  `unanswered_required_items`, and `warnings` grouping

## Blueprint Summary

The `bs-blueprint` repository is a Dataiku DSS webapp starter built with:

- Vue 3
- Vite
- Pinia
- Vue Router
- Tailwind CSS v4
- branded CSS design tokens
- `reka-ui` headless primitives
- `lucide-vue-next` icons
- a small local UI component layer instead of a heavy external component
  library

Core blueprint patterns:

- raw brand tokens live in `frontend/src/styles/tokens.css`
- `frontend/src/style.css` bridges those tokens into utility classes
- local UI primitives live in `frontend/src/components/ui/`
- page layout uses a reusable shell and sidebar pattern
- the blueprint prefers shared tokenized primitives over one-off component CSS
- no raw hex values should appear in components

Relevant blueprint files:

- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/styles/tokens.css`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/style.css`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/components/layout/AppSidebar.vue`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/layouts/DefaultLayout.vue`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/components/ui/EaButton.vue`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/components/ui/EaSelect.vue`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/components/ui/EaEmpty.vue`
- `/Users/li-hengfu/Documents/GitHub/bs-blueprint/frontend/src/views/ExampleView.vue`

## Current Prior-Auth UI State

The current prior-auth webapp already matches the blueprint at the framework
level in important ways:

- Vue 3
- Vite
- Pinia

Current frontend location:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src`

Key difference from the blueprint:

- the app is styled primarily through one large custom stylesheet:
  `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/style.css`
- controls are mostly native `button`, `select`, `input`, and `textarea`
- layout and badges are bespoke rather than built from a shared local component
  system

Important existing UI files:

- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/App.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/PatientSummary.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/ScopeSummary.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/ReviewerNoteCard.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/WorkflowNav.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/Screen1Page.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/Screen2Page.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/CriterionCard.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/Screen3Page.vue`
- `/Users/li-hengfu/Documents/GitHub/demo-prior-auth/webapps/prior_auth_review/src/components/ReviewSummary.vue`

## Migration Goals

The redesign should:

- align visual design with the company blueprint and Dataiku brand template
- introduce a reusable local UI primitive layer
- replace bespoke styling patterns with tokenized utility-driven styling
- preserve all current workflow behavior
- preserve all existing backend and store contracts
- improve consistency across the three workflow screens
- keep the current left-rail workflow concept, but make it feel like a
  Dataiku product rather than a standalone POC stylesheet

Current note:

- the store/runtime split remains intact, but Screen 3 rendering now depends on
  the revised deterministic payload buckets above

## Design Principles For This Migration

- preserve current architecture
- change visuals before behavior
- prefer shared primitives over repeated custom markup
- use local UI wrappers instead of introducing a third-party component library
- use Dataiku brand tokens and approved pairings
- keep Screen 2 status, progress, and review affordances explicit
- keep Screen 3 clearly deterministic and audit-oriented in its presentation
- keep the implementation incremental and reviewable

## Planned Phases

### Phase 1. Foundation

Introduce the blueprint-style frontend foundation into
`webapps/prior_auth_review`.

Add frontend dependencies:

- `tailwindcss`
- `@tailwindcss/vite`
- `reka-ui`
- `lucide-vue-next`
- `class-variance-authority`
- `clsx`
- `tailwind-merge`
- optionally `tw-animate-css` if useful for parity with the blueprint

Restructure styling:

- split the current monolithic `src/style.css`
- add `src/styles/tokens.css`
- rebuild `src/style.css` as the Tailwind + token bridge layer

Constraints:

- do not change screen behavior in this phase
- do not rewrite the store
- do not touch backend API code

### Phase 2. Local UI Primitive Layer

Create a small shared local UI kit modeled after the blueprint.

Planned files:

- `src/components/ui/EaButton.vue`
- `src/components/ui/EaSelect.vue`
- `src/components/ui/EaEmpty.vue`
- `src/components/ui/EaTextarea.vue`
- `src/components/ui/EaBadge.vue`
- `src/components/ui/index.ts`

Optional follow-up primitives if helpful:

- simple table primitives for Screen 3 summary layouts
- simple card/title wrapper components if repetition becomes high

Constraints:

- these primitives should be thin wrappers
- styling should come from shared tokens/utilities
- no hardcoded hex values in component files

### Phase 3. App Shell And Layout

Refactor the main shell to better match blueprint composition while keeping the
current workflow structure.

Planned files:

- update `src/App.vue`
- optionally add `src/layouts/WorkflowLayout.vue`
- optionally add `src/components/layout/AppSidebar.vue`

Target structure:

- stable branded left rail
- scroll-safe main content region
- consistent page header region
- constrained content width
- responsive stacked behavior on smaller screens

Important note:

- the app should not copy the blueprint sidebar literally
- it should preserve the prior-auth workflow sidebar content and adapt the
  visual shell only

### Phase 4. Shared Sidebar Cards

Restyle and normalize the left-rail summary blocks.

Files:

- `src/components/PatientSummary.vue`
- `src/components/ScopeSummary.vue`
- `src/components/ReviewerNoteCard.vue`
- `src/components/WorkflowNav.vue`

Goals:

- consistent card anatomy
- consistent label/value treatment
- branded but restrained visual hierarchy
- better form styling in reviewer metadata inputs
- workflow stepper aligned with the blueprint idiom

### Phase 5. Screen 1 Redesign

Refactor Screen 1 around shared primitives and tokenized layout.

Files:

- `src/components/Screen1Page.vue`
- `src/components/ScenarioSelector.vue`

Goals:

- convert native selects to `EaSelect`
- standardize section spacing and titles
- improve hierarchy between:
  - patient/policy selection
  - scope builder
  - route match preview
  - guard questions
  - CTA area
- preserve the current deterministic Screen 1 behavior exactly

### Phase 6. Screen 2 Redesign

Refactor Screen 2 into a more structured Dataiku-style review surface.

Files:

- `src/components/Screen2Page.vue`
- `src/components/CriterionCard.vue`

Goals:

- separate progress, review summary, and criteria list into clearer zones
- standardize chips for:
  - criterion kind
  - chart evidence state
  - final review state
  - source/origin
- improve the evidence panel presentation
- improve the clinician answer and comment inputs
- keep DSS progress details visible but more polished
- preserve all `local` and `dss` interaction behavior

Current state:

- the redesigned Screen 2 shell is implemented locally
- the `dss` streaming path is wired through the same page and cards
- live DSS validation of streaming/hydration/HITL presentation is still
  pending

### Phase 7. Screen 3 Redesign

Refactor Screen 3 into a deterministic summary dashboard pattern.

Files:

- `src/components/Screen3Page.vue`
- `src/components/ReviewSummary.vue`

Goals:

- promote readiness and criterion outcome counts into stronger summary tiles
- present satisfied, rejected, and unresolved criteria as mutually exclusive
  deterministic buckets
- keep “return to criterion” clear and secondary
- reduce visual repetition
- preserve deterministic Screen 3 ownership while improving the audited summary

Current state:

- implemented locally
- revised Screen 3 deterministic payload/UI grouping is complete
- validated against local fixture scenarios only

### Phase 8. Cleanup And Consolidation

After the visual refactor:

- remove obsolete legacy CSS blocks from `src/style.css`
- consolidate repeated display patterns into shared primitives or utilities
- verify no component is still using raw hex values or bespoke one-off colors
- keep the resulting system easy to extend

## File-By-File Migration Map

### New files expected

- `webapps/prior_auth_review/src/styles/tokens.css`
- `webapps/prior_auth_review/src/components/ui/EaButton.vue`
- `webapps/prior_auth_review/src/components/ui/EaSelect.vue`
- `webapps/prior_auth_review/src/components/ui/EaEmpty.vue`
- `webapps/prior_auth_review/src/components/ui/EaTextarea.vue`
- `webapps/prior_auth_review/src/components/ui/EaBadge.vue`
- `webapps/prior_auth_review/src/components/ui/index.ts`
- `webapps/prior_auth_review/src/layouts/WorkflowLayout.vue`
- optionally `webapps/prior_auth_review/src/components/layout/AppSidebar.vue`

### Existing files expected to change

- `webapps/prior_auth_review/package.json`
- `webapps/prior_auth_review/src/main.ts`
- `webapps/prior_auth_review/src/style.css`
- `webapps/prior_auth_review/src/App.vue`
- `webapps/prior_auth_review/src/components/PatientSummary.vue`
- `webapps/prior_auth_review/src/components/ScopeSummary.vue`
- `webapps/prior_auth_review/src/components/ReviewerNoteCard.vue`
- `webapps/prior_auth_review/src/components/WorkflowNav.vue`
- `webapps/prior_auth_review/src/components/Screen1Page.vue`
- `webapps/prior_auth_review/src/components/ScenarioSelector.vue`
- `webapps/prior_auth_review/src/components/Screen2Page.vue`
- `webapps/prior_auth_review/src/components/CriterionCard.vue`
- `webapps/prior_auth_review/src/components/Screen3Page.vue`
- `webapps/prior_auth_review/src/components/ReviewSummary.vue`

### Files expected to stay functionally stable

- `webapps/prior_auth_review/src/stores/priorAuthStore.ts`
- `webapps/prior_auth_review/src/Api.ts`
- `webapps/prior_auth_review/backend/*`

Current status:

- this assumption no longer fully holds
- the migration required UI-supporting updates in:
  - `webapps/prior_auth_review/src/Api.ts`
  - `webapps/prior_auth_review/src/stores/priorAuthStore.ts`
  - `webapps/prior_auth_review/backend/*`
  - `scripts/agent_flow/functions/screen_payload_helpers.py`
  - corresponding schema/docs under `scripts/schema_v4/`
- these changes were limited to supporting the redesigned deterministic Screen 3
  behavior and the local/DSS review flow

## Rollout Order

Recommended implementation order:

1. Foundation and dependencies
2. Shared UI primitives
3. Shell and sidebar layout
4. Shared sidebar cards
5. Screen 1
6. Screen 2
7. Screen 3
8. Cleanup

This order minimizes risk and keeps behavior stable while the visual system is
being introduced.

## Verification Plan

### Functional verification

- run `npm run type-check`
- run `npm run build`
- verify Screen 1 works end-to-end
- verify Screen 2 works in both `local` and `dss` modes
- verify Screen 3 still renders deterministic results after review
- verify “return to criterion” from Screen 3 still works

Current completed verification:

- `npm run type-check`
- `npm run build`
- local Screen 1 / Screen 2 / Screen 3 manual flows
- local fixture-backed Screen 2 -> Screen 3 transitions
- local Screen 3 return-to-criterion behavior

Still required:

- DSS-mode streaming progress rendering
- DSS-mode paused HITL review rendering
- DSS-mode resume/completion transition from Screen 2 to Screen 3

### UI verification

- verify desktop layout
- verify mobile/narrow-width layout
- verify left rail remains usable and readable
- verify contrast meets the existing Dataiku brand guidance
- verify all new controls have visible focus states
- verify loading and disabled states remain legible

### Non-goals for this migration

- no backend redesign
- no Store/API contract redesign
- no Structured Agent contract changes
- no change to the current workflow ownership model
- no expansion of scope beyond UI alignment and component-system cleanup

## Implementation Notes

- preserve the current architecture unless a UI-supporting change is strictly
  necessary
- update this document if the migration plan changes materially during
  implementation
- keep changes incremental and reviewable

## DSS Streaming Display Review Scope

The current DSS streaming display is centered in `Screen2Page.vue` and is fed
by normalized run-state polling from `priorAuthStore.ts` and
`backend/backend.py`.

Primary streaming UI elements:

- review-stage badge in `Screen2Page.vue`
- review progress hero and progress meter
- runtime card and queue-detail card
- progressive hydration of Screen 2 criteria through `screen_2_snapshot`
- HITL pause transition into the editable Screen 2 review surface

Important current limitation:

- this streaming presentation has been reviewed in code and exercised only
  through local assumptions/fixtures; it has not yet been validated against a
  live DSS-hosted run

## DSS Streaming Components Migration Plan

### Objective

Align the live DSS Screen 2 streaming experience with the redesigned webapp so
that:

- progress wording is clinician-friendly rather than engineering-oriented
- streaming components visually match the new Screen 2 design system and do not
  look like a separate runtime overlay
- streaming state transitions are stable and do not repaint stale data
- criteria do not appear prematurely before the Structured Agent has emitted a
  real Screen 2 snapshot
- the Screen 2 running, paused, and submit-resume states match the actual
  Structured Agent lifecycle

This plan is specifically for the live `dss` path. It does not change the
fixture-backed `local` path beyond keeping shared copy and presentation
consistent where appropriate.

### Current Findings

#### Finding 1. Overlapping polling can repaint stale state

Current behavior:

- `openScreen2()` starts polling and also awaits an immediate `pollRunState()`
- `submitReview()` does the same during the resume path
- `startPolling()` schedules repeated polling without an in-flight/request
  freshness guard

Impact:

- slower older responses can overwrite newer UI state
- progress, criteria, or stage copy can flicker backward
- clinicians may lose trust in whether the review is actually progressing

Target improvement:

- only the latest poll response should be allowed to update Screen 2 state
- running -> paused -> completed transitions should render once and remain
  stable

#### Finding 2. Placeholder criteria appear before a real Screen 2 snapshot

Current behavior:

- when `screen2` is still null, the store falls back to
  `buildPlaceholderCriterionRows(...)` from
  `selected_scope_context.selected_criteria_catalog`
- this is useful in local/fallback contexts but misleading in live DSS
  streaming before the agent has produced an actual review snapshot

Impact:

- the user can see criterion cards that look reviewable before the Structured
  Agent has actually prepared them
- the experience can imply that Screen 2 is "ready" while evidence gathering is
  still in progress

Target improvement:

- in live DSS mode, do not render placeholder criterion cards while the agent
  is still running and no real `screen_2_snapshot` has arrived
- instead, render progress-only messaging until the first streamed snapshot is
  available

#### Finding 3. "Hydration" language is too technical for clinicians

Current behavior:

- the Screen 2 running state still uses internal wording such as
  "hydrated/hydrating" in parts of the UI and docs

Impact:

- the message is accurate for engineers but not intuitive for healthcare
  providers
- it weakens confidence because the action described does not match how
  clinicians think about chart review

Target improvement:

- use plain clinical-review wording that describes what the Structured Agent is
  doing in user terms
- keep the same backend semantics while changing only the user-facing labels

#### Finding 4. Streaming UI still needs an explicit style-alignment pass

Current behavior:

- the streaming hero, runtime panel, queue-detail card, empty state, and
  paused-state transition already use the new component layer, but they still
  need to be treated as first-class Screen 2 surfaces rather than special
  runtime diagnostics

Impact:

- if the live DSS path keeps even subtle one-off spacing, tone, or badge
  patterns, the review can feel inconsistent exactly when the user most needs
  confidence in the workflow
- clinicians may read the streaming area as a technical status console instead
  of part of the eligibility-review experience

Target improvement:

- the live streaming surfaces should share the same card anatomy, typography,
  badge treatment, spacing rhythm, and background hierarchy as the rest of the
  redesigned Screen 2 page
- runtime detail should remain available, but visually secondary to the review
  workflow

### Recommended User-Facing Wording

These phrases should replace "hydrating/hydration" in the streaming UI where
they fit the run state:

- `Preparing the review`
- `Review in progress`
- `Gathering chart evidence`
- `Analyzing chart evidence`
- `Building the eligibility review`
- `Preparing criteria for review`
- `Review ready`

Recommended usage model:

- use one high-level stage badge for the overall state
- use a more specific body message for the current agent phase when known
- use the same wording consistently in the hero, runtime card, empty states,
  and any waiting copy

### Structured Agent Block Mapping

The Screen 2 Structured Agent has more backend blocks than the UI should
surface directly. The frontend should map multiple backend blocks into a small,
stable set of clinician-facing phases.

Recommended mapping:

- `init_state` + `plan_retrieval`
  - UI body text: `Preparing the review`
- `execute_plan` + `reason_one_criterion`
  - UI body text: `Gathering chart evidence`
- `accumulate_result` + `build_criterion_ui_map`
  - UI body text: `Preparing criteria for review`
- `evaluate_logic_tree`
  - UI body text: `Analyzing chart evidence`
- `prepare_screen_2_review_payload`
  - UI body text: `Building the eligibility review`
- `request_screen_2_human_review`
  - stage badge/body state: `Review ready`
- `emit_review_result_artifact`
  - generally do not expose as a distinct Screen 2 step
  - if needed during the Screen 2 -> Screen 3 handoff, use
    `Preparing final review`

Recommended generic fallback when no reliable block identifier is available:

- stage badge: `Review in progress`
- body text: `The review is in progress.`

Recommended per-criterion running copy:

- `Gathering chart evidence`

### Proposed UI Copy Mapping

#### Review-stage badge

Use:

- running: `Review in progress`
- hitl paused: `Review ready`
- completed: `Review complete`
- failed: `Review interrupted`
- submitting/resume path: `Preparing final review`

#### Progress hero body

Use:

- early run / retrieval plan setup: `Preparing the review`
- criterion loop: `Gathering chart evidence`
- logic reconciliation: `Analyzing chart evidence`
- payload assembly: `Building the eligibility review`
- pre-HITL assembly: `Preparing criteria for review`
- paused state: `The eligibility review is ready for clinician confirmation.`
- submit-resume state: `We are finalizing the clinician-approved review and preparing the submission summary.`

#### Runtime card

Use:

- `Live Structured Agent`
- supporting text:
  `Managed chart review with clinician confirmation.`

Replace:

- `Streaming criterion hydration with managed human review.`

#### Empty/loading states

Use:

- title: `Waiting for review criteria`
- description:
  `The eligibility review will appear here as chart evidence is prepared for clinician review.`

Replace wording that currently says the backend is "hydrating" the review.

### Streaming Style Alignment Requirements

The streaming components should stay inside the same visual language already
established by the redesigned Screen 2 surface.

#### Shared design requirements

- use the same tokenized card shells, border radius, border color, and shadow
  depth as the rest of Screen 2
- use the same font hierarchy:
  - mono uppercase labels for small metadata labels
  - serif headings for major review titles
  - sans body copy for explanatory/status text
- use the same badge system and status tones already used elsewhere in Screen 2
- keep runtime/queue details visually subordinate to the primary review
  progress message
- avoid introducing any special-purpose debug styling for the live DSS path

#### Progress hero

The progress hero should look like the primary Screen 2 status card, not a
separate streaming console.

Requirements:

- preserve the existing two-column layout with the narrative progress panel on
  the left and runtime/detail cards on the right
- keep the narrative panel as the visual anchor
- treat the progress meter as a branded supporting element rather than the main
  source of meaning
- ensure loading spinner, stage badge, and body copy align with the same
  spacing rules used by criterion and summary cards

#### Runtime and queue-detail cards

These cards should remain useful but secondary.

Requirements:

- keep them in the same background and border treatment as other supporting
  Screen 2 cards
- do not let queue-detail metadata dominate the page visually
- ensure labels such as `Runtime`, `Criteria`, and `Current criterion` use the
  same small-label styling as the rest of the redesign
- if information is unavailable, collapse gracefully rather than leaving empty
  technical placeholders

#### Waiting / empty state

Before the first real Screen 2 snapshot arrives, the empty state should feel
like part of the review flow.

Requirements:

- use the same `EaEmpty` style language already adopted elsewhere
- align title/description spacing with the redesigned card stack
- present "waiting for criteria" as a review-preparation step, not an error or
  technical backend lag

#### HITL paused state

The transition from running to clinician-editable review must feel seamless.

Requirements:

- once the agent pauses, the same progress shell should remain visible long
  enough to anchor the user, but the editable criterion cards should become the
  clear primary content
- the paused-state badge and message should match the same visual treatment as
  other "ready" states in the redesign
- there should be no abrupt style break between the running surface and the
  editable review surface

#### Submit / resume transition

The submit-resume path should visually read as the last step of Screen 2 and
the bridge into Screen 3.

Requirements:

- reuse the same progress hero shell rather than introducing a separate loading
  pattern
- keep the button disabled/loading treatment aligned with the new button
  system
- ensure the transition state does not visually regress to legacy styles

### Implementation Tasks

#### 1. Stabilize polling in `priorAuthStore.ts`

Update the live polling path so only the newest response mutates store state.

Implementation direction:

- add an in-flight guard and/or monotonically increasing poll request token
- discard late responses that are older than the latest issued request
- ensure `openScreen2()` and `submitReview()` cannot race their immediate poll
  call against the active interval in a way that repaints stale state

Files:

- `webapps/prior_auth_review/src/stores/priorAuthStore.ts`

Expected benefit:

- stable progress/state transitions
- no backward flicker in stage badge, criteria list, or Screen 2 snapshot

#### 2. Suppress placeholder criteria during live DSS running state

Update the criteria computation so placeholder rows are not shown in live DSS
mode before the first real streamed Screen 2 snapshot exists.

Implementation direction:

- keep placeholder rows available for local fixture/fallback usage where they
  remain useful
- for `dss` + `agentStatus === running` + `screen2 === null`, return an empty
  criteria list and rely on progress UI only
- once `screen_2_snapshot` exists, render the real criterion rows normally

Files:

- `webapps/prior_auth_review/src/stores/priorAuthStore.ts`
- `webapps/prior_auth_review/src/components/Screen2Page.vue`

Expected benefit:

- no premature reviewable cards
- clinicians see a clear distinction between "agent is working" and "criteria
  are ready to review"

#### 3. Replace technical streaming terminology in Screen 2

Update the Screen 2 streaming and waiting copy to the clinician-facing wording
above.

Implementation direction:

- remove "hydrating/hydration" from runtime copy, paused-state copy, and empty
  state copy
- centralize the stage/body wording so the same phrase is reused consistently
- keep engineering terminology only in docs or internal code comments, not in
  the UI

Files:

- `webapps/prior_auth_review/src/components/Screen2Page.vue`
- optionally `webapps/prior_auth_review/src/components/CriterionCard.vue`
- `scripts/schema_v4/frontend_webapp_contract_v1.md`
- `webapp-ui-migration.md`

Expected benefit:

- the webapp sounds like a clinical review tool rather than an engineering POC
- status messages become easier to understand quickly during live review

#### 3a. Align streaming surfaces with the redesigned Screen 2 visual system

Review the live-running, paused, and submit-resume states against the current
Screen 2 card system and normalize any remaining one-off styling.

Implementation direction:

- keep all streaming surfaces on the same tokenized card and badge system
- ensure progress, waiting, and paused states use the same spacing rhythm as
  criterion cards and summary tiles
- demote runtime diagnostics visually so they support the workflow instead of
  competing with it
- verify no streaming-specific copy block or empty state falls back to a legacy
  CSS pattern

Files:

- `webapps/prior_auth_review/src/components/Screen2Page.vue`
- `webapps/prior_auth_review/src/style.css`
- optionally shared primitives under
  `webapps/prior_auth_review/src/components/ui/`

Expected benefit:

- the live DSS experience feels like the same product as the local review flow
- streaming states look intentional and trustworthy rather than transitional or
  partially migrated

#### 4. Optional follow-up: expose phase-aware messaging from DSS state

If the live DSS run reliably exposes `current_block_id`, the frontend can map
that field to the phase labels above. If not, keep the simpler running-state
fallbacks.

Implementation direction:

- inspect actual live `current_block_id` values from `state.progress` or
  related run-state payloads
- add a frontend helper that maps backend block ids into the clinician-facing
  labels listed above
- fall back to generic running copy when the block id is absent or unknown

Files:

- `webapps/prior_auth_review/src/stores/priorAuthStore.ts`
- `webapps/prior_auth_review/src/components/Screen2Page.vue`
- optionally `webapps/prior_auth_review/src/uiLabels.ts`

Expected benefit:

- richer real-time progress messaging without exposing raw agent internals

### Verification Plan For Streaming Migration

#### Local verification

- run `npm run type-check`
- run `npm run build`
- verify local fixture-backed Screen 2 still renders correctly
- verify local copy changes did not regress the shared `local` path

#### DSS verification

Must be tested against a live DSS-hosted run after implementation.

Checklist:

- opening Screen 2 shows progress-only UI before any real criteria are ready
- no placeholder criterion cards appear before the first `screen_2_snapshot`
- progress badge and body text advance without flicker or backward repaint
- when the agent pauses for HITL review, the page switches cleanly to editable
  criteria
- the paused state wording reads naturally for clinicians
- after submission, the resume path transitions cleanly to Screen 3 without
  remaining stuck on Screen 2 progress
- unknown/failed states still show safe fallback copy
- the running, paused, and resume states all visually match the redesigned
  Screen 2 card/badge/spacing system
- runtime and queue-detail cards remain readable but clearly secondary to the
  main review workflow

### Out Of Scope

This streaming migration plan does not:

- redesign the Structured Agent graph
- change Screen 2 ownership boundaries
- alter Screen 3 deterministic summary logic
- change the clinician answer schema
- introduce new DSS backend contracts unless phase-aware progress mapping later
  proves necessary
