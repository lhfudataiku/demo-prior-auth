<div class="alert">
This is a demo-only release and should not be installed on customer instances.
</div>

# Release Notes #

## Version 0.2.0

### New feature: Agent Review pre-deployment guardrail

Version 0.2 adds a clinical quality-evaluation layer around the Prior
Authorization Review Agent. Clinical subject matter experts can evaluate a
candidate Structured Agent version against repeatable clinical cases before it
is used in the operational workflow.

Agent Review is separate from the Screen 2 clinician approval checkpoint. The
operational checkpoint supports completion of an individual prior authorization
request; Agent Review validates the agent's retrieval, evidence interpretation,
eligibility disposition, and reasoning quality across known cases.

Current v0.2 capabilities include:

- four reusable clinical cases for end-to-end review
- clinician-readable agent outputs and reference answers rather than raw JSON
- case-level eligibility guardrails and managed HITL trajectory checks
- per-criterion review of eligibility status, evidence quality, retrieval
  approach, and reasoning safety
- dedicated Retrieval Planner and Criterion Reasoning evaluation agents for
  targeted regression diagnosis
- review boundaries that exclude clinician comments and webapp edits from agent
  scoring and ground truth
- DSS completion handling that derives Screen 3 from the retained
  `screen_2_review_result` artifact, rather than attempting to parse the
  clinician-readable terminal Markdown

This feature provides a governed feedback loop for prompt refinement and
pre-deployment regression testing while retaining human ownership of the final
coverage decision.

## Version 0.1.1
- Redesign UI with Dataiku webapp framework.

## Version 0.1.0

### New feature: Prior authorization three-screen review web app

This release introduces the packaged clinician-facing workflow for prior authorization review:

- Screen 1 deterministic scope selection
- Screen 2 eligibility review and clinician confirmation
- Screen 3 deterministic final package review

### New feature: Structured Agent orchestration

This POC highlights the Dataiku Structured Agent as the core feature for HLS prior-authorization workflows. After deterministic Screen 1 scope resolution, the Structured Agent owns Screen 2: it accepts `subject_id` and scoped policy context, loads or generates a retrieval plan, executes criterion-level reasoning against chart evidence, evaluates the selected policy logic tree, prepares the clinician review payload, pauses at the managed human approval checkpoint, and returns the reviewed Screen 2 artifact for deterministic downstream transformation into Screen 3.

Current behavior includes:

- accepting `subject_id` and scoped policy context after deterministic Screen 1 resolution
- loading or generating a retrieval plan for the selected criteria
- executing criterion-level reasoning and building a criterion result map
- evaluating the selected cluster logic tree
- preparing the Screen 2 review payload for clinician validation
- pausing at the DSS-managed human approval checkpoint
- returning the reviewed Screen 2 artifact for deterministic Screen 3 generation

### Datasets and Connections

This release supports two explicit backend data-source modes:

- `local`
- `dss`

`local` mode reads fixture-backed CSV and JSON artifacts for deterministic demo execution.

`dss` mode reads DSS datasets and invokes the live Structured Agent path without silent fallback to `local`.

This release also packages the current FHIR-oriented EHR processing design and the semantic-model-driven retrieval layer used by the agent:

- Pathling-based FHIR data access patterns
- PySpark-based EHR ETL
- typed EHR evidence domains and reusable retrieval archetypes
- semantic clinical-note search for narrative qualifiers

### Coding & API

The backend is released as a Flask API with support for:

- Screen 1 bootstrap and advance
- local Screen 2 bootstrap
- DSS Screen 2 run start, poll, and HITL resume
- live run-state normalization for the frontend
- deterministic Screen 3 derivation from reviewed Screen 2 output
