<span id="version" style="color: grey; float: right">Version 0.2.0 draft</span><br/>

# Prior Authorization POC v0.2 Scoping Document

## Purpose

Version 0.2 adds an Agent Review layer to the prior-authorization POC.

The goal is to let clinical subject matter experts evaluate the Structured
Agent's Screen 2 eligibility reasoning across known clinical cases, including
case-level outcomes and per-criterion evidence quality.

This release does not change the core v0.1 workflow ownership:

- Screen 1 remains deterministic backend scope selection.
- Screen 2 remains Structured Agent orchestration.
- Screen 3 remains deterministic backend/webapp generation after review.

The v0.2 scope adds a repeatable review and annotation workflow around saved
Structured Agent runs.

Reference:

- Dataiku Agent Review:
  https://doc.dataiku.com/dss/latest/agents/agent-review.html

## Background

The v0.1 POC already includes:

- a deterministic Screen 1 scope-selection flow
- a Structured Agent that runs Screen 2 eligibility reasoning
- a webapp review path for clinician confirmation
- deterministic Screen 3 generation from reviewed Screen 2 outputs
- four clinical cases already executed through the Structured Agent

The existing case artifacts are stored under:

- `scripts/artifacts/fixtures/structured_agent_requests`

Each case includes:

- `*_screen_2_agent_request.json`
  - the Structured Agent input request
- `*_agent_context.json`
  - the saved DSS block-graph context after the Structured Agent run

Initial target cases:

- `0059`
- `0314`
- `0655`
- `0685`

## v0.2 Objective

The major new feature is Agent Review for clinical annotation of prior-auth
eligibility reasoning.

Clinicians should be able to inspect a completed Structured Agent run and
annotate whether the agent's eligibility output is clinically supported by the
chart evidence it retrieved.

The review should answer:

- Did the agent reach the correct patient eligibility disposition?
- Did each criterion use appropriate clinical evidence?
- Did the agent mark missing or ambiguous evidence correctly?
- Did the agent cite enough evidence for a reviewer to audit the result?
- Did any criterion contain an unsafe, unsupported, or incomplete conclusion?

## Target Persona

Primary persona:

- clinician reviewer / clinical SME

The reviewer is responsible for validating the Structured Agent's clinical
reasoning, not for completing the prior authorization request in the operational
webapp.

The reviewer needs to evaluate:

- patient eligibility summary
- criterion-level chart evidence
- criterion-level status and `meets_criterion` adjudication
- unresolved or ambiguous criteria
- evidence sufficiency and relevance
- reasoning failures or missing evidence

## Agent Review Model

Agent Review should treat each clinical case as a test.

The test input should be derived from:

- `*_screen_2_agent_request.json`

The Agent Review answer and reference should use the same clinician-readable
Markdown summary. The production agent builds that summary from the deterministic
Screen 2 payload after the HITL decision; it is not a raw JSON payload.

When Agent Review is configured to automatically accept the human-in-the-loop
tool validation request, the final agent output is the clinician-readable
Markdown `agent_review_summary`. Its case and UI disposition comes from the
nested `screen_2_review_result.reviewed_screen_2_payload`; its per-criterion
requirement-assessment text comes from the agent-owned `criterion_result_map`
and `retrieval_plan_v1` state objects.

The wrapper fields such as `approval_status`, `approved_criterion_answers`,
`review_metadata`, and `human_validated` can be used to verify that the HITL
path completed, but the clinical reasoning review should still be anchored on
the Screen 2 payload inside the result.

The review material can be extracted from saved Structured Agent contexts in:

- `*_agent_context.json`

The saved context currently contains DSS block-graph state fields such as:

- `selected_scope_context`
- `retrieval_plan_v1`
- `criterion_result_map`
- `criterion_ui_map`
- `logic_evaluation`
- `screen_2_payload`
- `screen_2_review_tool_input`
- `screen_2_review_result`
- `agent_review_summary`

For Agent Review, the preferred clinical reference answer is the agent-produced
Screen 2 payload, not the entire saved agent context. Depending on HITL
configuration, that payload may appear either as pause-time tool input or as a
nested field in the final review result.

The current `NkBiV9OM-v2` graph routes from `prepare_screen_2_review_payload`
into the `request_human_review` block. Because that block uses a managed
human-approval tool, a normal Agent Review run may pause before a final
human-review decision is returned to the agent.

At that pause, the pending tool validation request exposes the review payload
as:

- `review_request.screen_2_payload`

This is the object clinicians should review for v0.2 clinical annotation. The
post-approval tool output is `screen_2_review_result`; that object wraps
`reviewed_screen_2_payload`, `approved_criterion_answers`, and review metadata.
If Agent Review is configured with a default HITL decision such as
`always accept`, it validates the final `agent_review_summary` Markdown. The
per-case and per-criterion review content should be generated from
`screen_2_review_result.reviewed_screen_2_payload`, excluding human-entered
comments and edits.

## Review Boundary

Agent Review evaluates the Structured Agent output, not the webapp clinician
edit session.

The final agent context may include clinician comments entered from the webapp.
Those comments are non-deterministic human inputs and must be excluded from the
Agent Review ground truth and scoring model.

Do not use the following as correctness labels:

- webapp-entered clinician comments
- clinician free-text comments inside `clinician_input`
- clinician comments inside `criterion_answers`
- comments returned through `approved_criterion_answers`
- review metadata comments from the human approval step

These fields may be displayed only as contextual audit metadata if needed, but
they should not determine whether the Structured Agent passed or failed a case
or criterion.

The review should instead focus on deterministic agent-generated material:

- `criterion_result_map`
- `criterion_ui_map.chart_result`
- `criterion_ui_map.ui_resolution`
- `screen_2_payload.payload.criteria[].chart_result`
- `screen_2_payload.payload.criteria[].ui_resolution`
- `logic_evaluation`
- selected scope labels and identifiers from `selected_scope_context`

## Case-Level Guardrail

Each Agent Review test has one case-level expectation trait. It is the
high-level pass/fail guardrail used to prompt clinician follow-up, not a
replacement for the detailed reasoning traits.

The main end-to-end suite is `Oh8ieqexla`. Its expectations are deliberately a
case-level guardrail, using fields visible in the final
`agent_review_summary` Markdown:

- Screen 2 review status
- selected-cluster eligibility status
- satisfied, not-satisfied, and unresolved criterion counts
- clinician-readable final output rather than raw JSON
- successful retrieval and managed HITL completion in the trajectory

The reference answer remains more detailed than the expectations so the
per-criterion traits can compare the final summary against the v1.2 clinical
baseline.

Suggested case-level metrics:

- case pass rate
- failed case count by policy
- failed case count by selected cluster
- unresolved-case rate
- reviewer disagreement rate
- regression count between agent versions

## Per-Criterion Quality Traits

Per-criterion metrics are in scope for v0.2.

Each criterion row should be reviewable independently. This is important because
a case-level pass/fail can hide whether the agent succeeded on most criteria but
failed on one clinically important requirement.

The detailed traits are evaluated for every criterion in the review summary.
They explain why a case-level guardrail passed or failed:

- criterion id
- criterion kind
- prompt
- chart evidence status:
  `Found | Missing | Ambiguous | Unreviewed`
- agent `meets_criterion`
- agent display state
- eligibility status:
  `correct | incorrect | not_reviewable`
- evidence quality:
  `complete | partially_complete | irrelevant | missing`
- retrieval approach:
  `correct | partially_correct | incorrect | not_reviewable`
- reasoning quality:
  `complete_with_sufficient_evidence | incomplete_but_safe | unsafe_conclusion_due_to_incomplete_reasoning | unsafe_conclusion_without_sufficient_evidence | other`
- reviewer note

The main-suite trait configuration is:

- `Eligibility status`: reference required
- `Evidence quality`: reference required
- `Retrieval approach`: reference required; compare only the displayed
  archetype and strategy
- `Reasoning quality`: reference required

The terminal summary exposes only the modifier and disqualifying-clause
assessments needed to audit clinical reasoning. It does not expose planner-only
fields such as `semantic_model_entities` or normalized time anchors. Those
fields remain the responsibility of the Retrieval Planner Evaluation Agent
review, not the main-suite traits. Each trait must explain its rating in a
review note. Requirement-assessment text is agent-owned and excludes clinician
comments and edited answers.

Trait interpretation rules:

- expectation traits evaluate only the explicitly listed expectations; they do
  not infer additional requirements from a fuller reference answer
- `Found`, `Missing`, and `Ambiguous` are distinct evidence-status values and
  must match exactly when a trait compares them to a reference
- a conservative unresolved result may pass evidence-quality review when it
  cites relevant context and identifies the missing fact; it must not be marked
  incorrect merely because the evidence needed for resolution is absent
- a `Found` / `true` result is unsafe when the reference leaves a qualifier or
  exclusion unresolved unless the answer cites direct evidence resolving that
  exact fact

Suggested per-criterion metrics:

- criterion correctness rate
- evidence sufficiency rate
- missing-evidence false positive rate
- missing-evidence false negative rate
- ambiguous-status appropriateness rate
- conflict-rate between chart evidence and final UI resolution
- unsupported-satisfied count
- unsupported-not-satisfied count
- not-reviewable count

## Traits

Automated traits may be added to support reviewer triage, but they should not
replace clinician review in v0.2.

Candidate traits:

- output is clinician-readable Markdown with every scoped criterion represented
- every selected criterion has a result
- `meets_criterion=true` only when `status=Found`
- every `Found` criterion has at least one supporting source or clear
  justification
- every unresolved criterion is represented as `Missing`, `Ambiguous`, or
  `Unreviewed`
- Screen 2 criterion count matches
  `selected_scope_context.selected_criteria_catalog`
- no Screen 3 payload is emitted by the Structured Agent

Human clinician feedback remains the authoritative review signal.

## Component Evaluation Agents

Two independent Structured Agents create review seams without redesigning the
production Screen 2 orchestration:

- `POEllEzU` - Retrieval Planner Evaluation Agent
  - uses the production `retrieval_planner_agent_prompt_v1_2.md` and the
    unchanged `retrieval_plan_v1` contract
  - accepts the normal Screen 2 request and renders the planned retrieval for
    every scoped criterion as clinician-readable Markdown
  - shows each criterion's data targets, required clinical qualifiers, and
    whether a disqualifying clause applies
- `2p7dFkWk` - Criterion Reasoning Evaluation Agent
  - uses the production `criterion_reasoning_agent_prompt_v1_2.md` and the
    `current_reasoning_result` contract, including internal qualifier and
    exclusion assessments
  - accepts `session_id`, `subject_id`, `policy_id`, and one
    `current_plan_item` from `retrieval_plan_v1.plan_items`
  - renders the criterion, retrieval approach, adjudication, justification,
    and cited structured/note evidence as clinician-readable Markdown
  - also renders the governing data targets, required clinical qualifiers,
    disqualifying-clause flag, and time reference for review
  - renders the reasoner's per-qualifier and disqualifying-clause assessments
    in a clinician-readable Requirement Assessment section

These component agents are evaluation harnesses. They do not replace the
production agent or add state keys to its response contract.

Evaluation ownership:

- `Oh8ieqexla` is the four-case end-to-end guardrail for final
  `agent_review_summary` output, case disposition, and HITL trajectory.
- `LimK6lZiKi` is the retrieval-planner authority for execution hints and
  time-constraint normalization.
- `Fqf1q4nCNT` is the criterion-reasoning authority for evidence status,
  `meets_criterion`, cited evidence, and reasoning safety.

## Current Evaluation Status

The v1.2 planner and criterion-reasoner prompts are synchronized between the
production agent and the component evaluation agents:

- production Structured Agent: `NkBiV9OM-v2`
- Retrieval Planner Evaluation Agent: `POEllEzU`
- Criterion Reasoning Evaluation Agent: `2p7dFkWk`

The production planner and reasoner blocks use the same prompt content and LLM
configuration as their corresponding component evaluation blocks. The observed
full-flow divergence is therefore an execution-time reliability issue, not an
accidental production-prompt drift.

### End-to-End Baseline

Agent Review run `5` of `Oh8ieqexla` is the v1.2-aligned four-case baseline.
All four test cases failed the aggregate guardrail because Agent Review judges
three executions per test and requires consistent safe behavior. A case failure
does not mean that every execution was wholly incorrect.

| Policy | Observed run-5 pattern | Clinical interpretation |
| --- | --- | --- |
| `0059` | One execution incorrectly satisfied the exclusion; one had a structured-retrieval failure; one matched the expected result. | The agent sometimes infers absence of COPD-diagnostic intent from chart silence. |
| `0314` | Two executions correctly returned unresolved CD20 confirmation; one promoted the result to satisfied and then failed the HITL handoff. | CLL and flow/cytometry confirmation do not by themselves prove the policy-required CD20-positive result. |
| `0655` | One execution matched the reference; other executions promoted no medication records to an exclusion pass and/or diagnosis-only evidence to active moderate/severe UC. | Retrieval absence is being confused with documented absence, and diagnosis is being overread as activity/severity. |
| `0685` | All executions treated the lung-cancer criterion as satisfied; exclusion criteria were also intermittently satisfied from absent medication records. | The clinical narrative is meaningful, but the agreed strict policy baseline remains unresolved without direct confirmation of all required stage and histology facts. |

Recurring failure patterns are:

- interpreting "no matching records" or a silent chart as documented absence
  for an exclusionary criterion
- treating a qualifying diagnosis as sufficient evidence for a separate
  activity, severity, stage, response, or confirmation qualifier
- treating a semantic-model or query failure as ordinary missing clinical
  evidence
- allowing an LLM to serialize the final large HITL payload, which produced one
  malformed `0314` request in run `5`

The current clinician-readable `agent_review_summary` accurately renders the
Screen 2 payload it receives. It is not the source of the incorrect clinical
adjudications.

### Component Baseline

The component suites demonstrate that the desired reasoning behavior is
possible, but they are not yet sufficient proof of production reliability:

- `LimK6lZiKi` run `6` passed its four retrieval-planner tests. The planner's
  high-level archetypes and retrieval strategies are not the leading suspected
  source of the production failures.
- `Fqf1q4nCNT` run `2` showed stable correct behavior for the `0059` criteria,
  but its `0314` test was skipped and its `0685` advanced-NSCLC test returned
  the overly permissive satisfied decision in two of three executions.
- The isolated test harness supplies a curated `current_plan_item`; the
  production agent generates its plan, loops through several criteria, carries
  more request context, and completes the HITL handoff. Component and
  production results therefore must be compared with execution trace evidence,
  not assumed to be interchangeable.

## Planned Reliability Revision

The near-term revision preserves the v0.1/v0.2 architecture and current
webapp-facing payload contract. It adds traceability and deterministic safety
checks around the existing reasoner rather than redesigning Screen 2.

### Design Principles

- Preserve the existing clinician-facing `current_reasoning_result` fields for
  payload and webapp helpers while extending the internal result with explicit
  qualifier and exclusion assessments.
- Preserve the raw LLM adjudication for audit; never overwrite it in place.
- Use a validated result for the logic tree, UI resolution, Screen 2 payload,
  and clinician-facing final summary.
- Keep planner-only implementation detail out of the default clinician review
  display, while making it available in execution trace and component review.
- Treat retrieval operational failures separately from missing patient evidence.

### Phase 1: Plan Parity Trace

The first change is observability, not clinical decision logic.

Implementation status: deployed to `NkBiV9OM-v2`. The production initializer
now creates `criterion_trace_map`, and the accumulator writes an immutable
snapshot of each plan item and raw reasoner result without changing
`criterion_result_map`, the logic tree, or the webapp/HITL payload.

`POEllEzU` now displays normalized time fields, and `LimK6lZiKi` asserts data
targets plus time type, reference column, and anchors. Its first strengthened
run (`8`) surfaced planner instability rather than a trace implementation
failure: `0059` intermittently adds `condition` to an `ARC_note_only` plan, and
`0314` intermittently adds `observation` to the CD20 composite plan. These
expectation failures are retained as useful plan-parity regression signals.

1. Initialize `criterion_trace_map` in `set_state_entries`.
2. In `accumulate_results`, persist the exact `current_plan_item` used for
   each criterion alongside the raw reasoning result.
3. Retain planner fields needed to compare production with `Fqf1q4nCNT`:
   archetype, retrieval strategy, semantic entities, qualifiers,
   disqualifying-clause flag, query fragment, and time constraint.
4. Continue placing the current clinical result in `criterion_result_map` so
   the webapp contract remains unchanged.
5. Extend `LimK6lZiKi` expectations to validate the full execution hints, not
   only the displayed archetype and strategy.
6. Add Agent Review trajectory checks that each expected criterion received one
   corresponding plan item and no unexpected criterion was planned.

### Phase 2: Explicit Qualifier and Exclusion Adjudication

The reasoner result now records how each planner-required modifier and
disqualifying clause was adjudicated, rather than relying only on a single
criterion-level status.

- `qualifier_assessments` contains exactly one item per planned qualifier, with
  the exact required clinical fact, its evidence status, and a compact
  normalized value when available.
- `disqualifying_clause_assessment` is `null` when no exclusion is planned;
  otherwise it records the named disqualifying fact, its evidence status, and
  whether it is directly documented as present or absent.
- The criterion-level result can be `Found`/`true` only when every required
  baseline fact, qualifier, temporal rule, and exclusion is directly resolved
  in favor of the criterion.
- These fields are retained in `criterion_result_map` and
  `criterion_trace_map` for component and integration review. They are not
  exposed in the default Screen 2 `chart_result` until a clinician-facing
  presentation is intentionally designed.

### Library-First Python Block Migration

The production Structured Agent `NkBiV9OM` currently contains five
`PYTHON_CODE` blocks:

- `accumulate_results`
- `logic_tree_evaluator`
- `build_criterion_ui_map`
- `prepare_screen_2_review_payload`
- `output_format`

The repository already owns most of the pure domain helpers under
`scripts/agent_flow/functions`, but the live graph still duplicates state
orchestration and summary-formatting code inline. This creates a versioning
risk: local library behavior and deployed block code can drift.

The migration objective is to keep only a stable DSS runtime adapter in each
inline block and move all deterministic behavior into versioned project-library
modules.

Migration status: the local branch now contains the explicit-runtime library
and pure summary helper. `python_code_blocks.py` is retained only as a local
simulation compatibility adapter. The five live `NkBiV9OM` DSS block bodies
now use their minimal explicit-runtime wrappers; future behavior changes should
be made in the versioned library and deployed through that wrapper contract.

#### Runtime Boundary

Do not import the current global-state wrappers directly from a DSS block. DSS
injects `state` and `scratchpad` into the inline block's global namespace; an
imported module cannot safely discover those runtime globals by inspecting its
own module namespace.

Library functions must accept runtime dependencies explicitly:

```python
def accumulate_current_reasoning_result(state, scratchpad, trace):
    ...
```

Each DSS block then remains a minimal callable adapter:

```python
from scripts.agent_flow.functions.screen2_agent_runtime import (
    accumulate_current_reasoning_result,
)

def accumulate_current_reasoning_result_block(trace):
    accumulate_current_reasoning_result(
        state=state,
        scratchpad=scratchpad,
        trace=trace,
    )
```

The wrapper is the only code allowed to depend on DSS-injected globals. The
library is ordinary Python and can be unit-tested outside DSS.

#### Target Library Layout

```text
scripts/agent_flow/functions/
  screen2_agent_runtime.py       # Explicit state/scratchpad orchestration
  screen2_summary_helpers.py     # Pure clinician-readable summary rendering
  screen_payload_helpers.py      # Existing Screen 2/3 payload transformations
  logic_tree_helpers.py          # Existing logic-tree evaluation
  common.py                      # Shared state types and scope access
```

`screen2_agent_runtime.py` should own:

- state-default initialization
- criterion-result parsing, accumulation, and trace capture
- logic evaluation from state
- UI-map construction from state
- Screen 2 payload construction from state
- Screen 2 review-tool input construction from state

`screen2_summary_helpers.py` should own the pure Markdown construction for
`agent_review_summary`. The output block should only call the formatter and
assign the returned text to state.

#### Block Migration Map

| Current block | Versioned library responsibility | DSS wrapper responsibility |
| --- | --- | --- |
| `accumulate_results` | parse raw reasoning output, preserve `criterion_trace_map`, mutate result map, write trace details | pass `state`, `scratchpad`, and `trace` |
| `logic_tree_evaluator` | derive and persist `logic_evaluation` | pass `state` and `trace` |
| `build_criterion_ui_map` | build and persist deterministic UI map from scope, result map, answers, and retrieval plan | pass `state` and `trace` |
| `prepare_screen_2_review_payload` | build Screen 2 payload and review-tool input, including fallback UI-map construction | pass `state` and `trace` |
| `output_format` | parse review result and produce clinician-readable Markdown | assign summary to state and emit trace metadata |

The migration also removes dormant inline dependency risks. For example, the
current deployed review-payload block has a fallback path that calls UI-map and
scope helpers not imported by that block; it succeeds only when the parallel
UI-map block has already populated state.

#### Migration Order and Gates

1. Extract `output_format` into a pure summary helper and test representative
   approved, rejected, and malformed review results.
2. Migrate `logic_tree_evaluator` and `build_criterion_ui_map`, which already
   have stable pure helper functions.
3. Migrate `prepare_screen_2_review_payload`; test both normal and fallback
   UI-map paths.
4. Migrate `accumulate_results`; test valid JSON, malformed JSON, missing
   criterion IDs, repeated criterion IDs, and immutable plan-trace capture.
5. Replace each live DSS block with its small explicit wrapper only after its
   library function passes local tests.
6. After each block cutover, run fixture regressions plus the relevant
   component Agent Review suite before migrating the next block.
7. Retire or reduce the existing `python_code_blocks.py` global-state
   compatibility layer after all production wrappers use the explicit-runtime
   library.

This refactor preserves all existing Screen 2, webapp, HITL, and Agent Review
payload contracts. It is a maintainability and deployment-versioning change,
not a clinical reasoning behavior change.

### Phase 2: Explicit Retrieval Outcomes

The reasoner currently receives prose tool responses. The two retrieval tools
need a shared envelope that distinguishes successful evidence retrieval from
successful zero-match retrieval and an operational failure:

```json
{
  "outcome": "success | no_matching_records | retrieval_error",
  "tool": "string",
  "message": "string",
  "records": [],
  "error_detail": null
}
```

Required changes:

1. Update `EHR_Query_Tool` and `Clinical_note_semantic_search_tool`, or insert
   deterministic wrappers around them, to return the envelope while preserving
   original source content.
2. Extend the reasoner output additively with retrieval-outcome provenance.
3. Require the reasoner to treat `retrieval_error` as incapable of proving a
   positive decision.
4. Require the reasoner to treat `no_matching_records` as retrieval absence,
   not documentation that a patient lacks a disqualifying drug, regimen, or
   request intent.
5. Add component and end-to-end test fixtures for all three outcomes before
   revising clinical prompt language again.

This phase crosses the boundary of the `criterion_reasoning` core loop because
the retrieval calls occur inside that block. A downstream block can interpret
preserved outcomes, but cannot reliably reconstruct a tool execution error from
free-text evidence after the fact.

### Phase 3: Deterministic Criterion Safety Validation

Add a Python validation block immediately after `criterion_reasoning` and
before `accumulate_results`.

The block should receive the raw `current_reasoning_result`, current plan item,
and normalized retrieval outcomes. It should write a separate validated result
and safety record, conceptually:

```json
{
  "plan_item": {},
  "raw_reasoning_result": {},
  "validated_reasoning_result": {},
  "safety_validation": {
    "status": "passed | downgraded",
    "rule_ids": [],
    "reason": "string"
  }
}
```

Initial deterministic downgrade rules:

- `exclusion_requires_direct_negative_evidence`: do not allow `Found/true`
  when a disqualifying clause is supported only by no records, silence, or
  unrelated evidence.
- `all_qualifiers_must_be_addressed`: do not allow `Found/true` when a required
  activity, severity, stage, response, or confirmation qualifier has not been
  directly addressed.
- `composite_confirmation_required`: do not allow diagnosis evidence alone to
  satisfy a criterion requiring a biomarker, pathology, imaging, flow, or
  similar additional clinical confirmation.
- `retrieval_error_cannot_prove_positive`: do not allow a failed retrieval leg
  to support a positive clinical conclusion.

The validator must preserve the raw result for audit. It may downgrade a result
to `Missing/false` when no evidence addresses the required fact, or to
`Ambiguous/false` when evidence is incomplete or conflicting. The validated
result, rather than the raw LLM result, becomes the input to
`accumulate_results`, `logic_tree_evaluator`, `build_criterion_ui_map`, and the
final Screen 2 payload.

### Phase 4: Evaluation Synchronization

After each production change, apply the same validation implementation to the
Criterion Reasoning Evaluation Agent `2p7dFkWk`.

- Its final formatted output should distinguish planned checks, raw reasoner
  decision, final validated decision, safety validation outcome, and cited
  evidence.
- `Fqf1q4nCNT` references and expectations should score the final validated
  decision, while retaining the raw decision for diagnosis.
- `Oh8ieqexla` should continue to score clinician-readable final output and
  case-level status. Add validator trajectory checks and, when useful, a
  dedicated safety-validation trait.
- The planner agent `POEllEzU` remains the authority for plan construction;
  it should display and test all planner hints used in the production trace.

### Deferred Architecture Objective: Deterministic HITL Handoff

The `request_human_review` core loop currently asks an LLM to serialize the
large `screen_2_review_tool_input` state object into a tool call. The malformed
`0314` execution shows that this boundary is not deterministic enough for a
clinician workflow.

Replacing it with a direct state-to-tool binding or Python adapter is a future
Structured Agent architecture objective. It is deliberately deferred from the
near-term reliability revision because it requires a separate design,
regression suite, compatibility review, and controlled cutover. Until then,
`Oh8ieqexla` must retain HITL trajectory checks and explicitly report handoff
errors as operational failures rather than clinical outcomes.

## In Scope

v0.2 includes:

- define the four existing clinical cases as Agent Review tests
- map `*_screen_2_agent_request.json` into Agent Review test inputs
- map `*_agent_context.json` into reviewable case outputs
- expose case-level review fields for clinician SMEs
- expose per-criterion review fields and metrics
- exclude webapp clinician comments from ground truth and scoring
- document the case artifact contract
- document repeatable run comparison expectations for future agent versions

## Out Of Scope

v0.2 does not include:

- new policy ingestion
- new clinical cases beyond the four existing cases
- new Screen 1 scope-selection behavior
- new Screen 3 generation targets
- FHIR export
- payer submission integration
- replacing the current webapp review workflow
- using clinician free-text comments as ground truth
- retraining or re-prompting the agent from clinician annotations

## Success Criteria

The v0.2 scope is successful when:

- all four existing clinical cases are represented as Agent Review tests
- each test can be reviewed at the case level
- each criterion can be reviewed independently
- clinicians can mark case and criterion correctness with comments
- clinician-entered webapp comments are excluded from scoring and ground truth
- Agent Review can distinguish deterministic agent behavior from human edits
- future Structured Agent versions can be compared against the same cases

## Implementation Notes

The implementation should preserve the existing release architecture.

Recommended artifact mapping:

- test query/input:
  `*_screen_2_agent_request.json`
- agent output/context:
  `*_agent_context.json`
- answer/reference display:
  `agent_review_summary`, clinician-readable Markdown generated from
  `screen_2_review_result.reviewed_screen_2_payload`
- clinical source data:
  `reviewed_screen_2_payload.payload.selected_scope_display`, criteria,
  chart results, UI resolution, and logic evaluation

If the saved `screen_2_review_result` contains human approval edits or comments,
use it cautiously. It can help confirm workflow completion, but wrapper fields
and human-entered comments should not be the primary objects used to judge the
Structured Agent's independent reasoning.

For Agent Review tests, both the expected reference and the final answer should
be the same Markdown structure. The raw `*_agent_context.json` files remain
source artifacts for extracting and auditing deterministic fields; they are not
rendered directly to clinician reviewers.

When Agent Review runs the live `NkBiV9OM-v2` graph, the reviewable payload is
expected to appear at the HITL pause as pending tool-call input:

- `hitl_payload.review_request.screen_2_payload`

If Agent Review requires a completed final answer rather than a paused
tool-validation request, configure Agent Review to auto-accept the HITL tool
request and validate the returned `agent_review_summary`, while grounding the
reference in the nested `reviewed_screen_2_payload`.

## Open Questions

- Should per-criterion reviewer notes be free text only, or should they require
  a controlled issue category?
- Should `needs_discussion` be separate from `fail`, or represented as a failed
  case with a discussion flag?
- Should Agent Review tests include a clinician-authored reference answer for
  each criterion, or only reviewer annotations after each run?
- Should automated traits be configured in v0.2 or deferred until v0.2.1 after
  clinician annotation patterns stabilize?
- Should the review dataset become a versioned artifact in `policy_artifacts`,
  or remain a separate review/evaluation asset?
