# Prior Auth V4 Schema

## Goal

This schema is designed for a clinician-facing prior-authorization webapp with
the following runtime workflow:

1. resolve the request from billing code
2. prompt for phase only when the policy explicitly distinguishes phase logic
3. if the selected billing code is not covered or investigational, terminate
   the workflow immediately
4. ask only route-level clinical guards that truly apply before condition
   selection
5. show the shortlist of condition clusters for the selected route and phase
6. after the clinician selects a condition cluster, ask any cluster-entry
   guards that apply only to that route/phase/cluster
7. materialize only the selected cluster criteria
8. prefill chart-backed evidence after route/phase/cluster selection using a
   downstream retrieval planner

This schema is intentionally:

- clinician-workflow-first
- clinical-only
- retrieval-light at parse time

## Design Principles

- The parser should model patient clinical eligibility only.
- Administrative, benefit, provider, and site-of-care logic must be excluded.
- Billing code is the primary request router.
- A request route should represent one policy-defined request family, not one
  billing code.
- If the policy groups multiple covered billing codes under the same narrative
  criteria, those billing codes should stay together in one shared route.
- Separate routes are appropriate only when the policy text gives different
  clinical logic, different terminal coverage outcomes, or clearly distinct
  request families.
- Billing codes listed as not covered or investigational in the policy code
  table should produce terminal request routes.
- Narrative request-level limitations on otherwise covered billing codes should
  become clinical guards, not terminal routes.
- Diagnosis exclusions listed in ICD tables should not be preserved in the
  primary artifact unless they directly define a request-level billing-code
  routing outcome.
- Phase is prompted only when the policy explicitly distinguishes initial,
  continuation, reauthorization, or another phase-specific branch.
- Condition clusters should prioritize code-table inclusion diagnoses over
  narrative disease examples.
- Diagnosis-defined clusters must retain diagnosis-grounded effective logic that downstream retrieval can execute; diagnosis metadata alone is not sufficient, but that logic may be represented by either a standalone diagnosis criterion or a composite disease-state criterion.
- Narrative disease examples should not become separate clusters when they are
  already subsumed by a covered diagnosis code range in the policy code table.
- Continuation clusters may inherit diagnosis scope from initial clusters when
  the continuation policy language refers back to the initial covered
  indications.
- Even when continuation language is shared, continuation clusters should stay
  disease-specific when those inherited diseases are clinician-selectable
  branches.
- Repeated logic across multiple clusters should be factored into reusable
  logic profiles instead of duplicated verbatim.
- Retrieval planning is not the parser's job; the parser should define what must
  be proven, not how to query the EHR.

## Schema Relationships

- `request_routes` own billing-code-first request-family routing.
- `route_guards` own pre-cluster clinical gates.
- `cluster_entry_guards` own post-selection pre-review clinical gates.
- `condition_clusters` own clinician-selectable disease or scenario scope.
- `criteria_catalog` owns criterion decomposition, including standalone versus composite fact modeling.
- `logic_root` owns boolean composition of already-defined criteria and guards.
- Downstream retrieval planning and adjudication should trust parser-defined criterion decomposition rather than inventing new criteria.

## Artifact 1: policy_master_v4

### Purpose

Canonical long-term memory of the parsed policy for runtime routing and
downstream retrieval planning.

### Top-level fields

- `policy_id`
- `document_type`
- `title`
- `source`
- `billing_code_sets`
- `request_routes`
- `route_guards`
- `cluster_entry_guards`
- `condition_clusters`
- `logic_profiles`
- `criteria_catalog`
- `notes`

## `billing_code_sets`

Use for both request billing codes and diagnosis code-table entries.

Each item:

```json
{
  "code": "string",
  "system": "CPT | HCPCS | ICD-10 | Other | UNKNOWN",
  "description": "string or UNKNOWN",
  "code_role": "request | diagnosis_inclusion | related | UNKNOWN",
  "coverage_status": "covered | not_covered | investigational | related | UNKNOWN",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. Request billing codes must preserve covered versus not-covered versus
   investigational status when stated by the policy.
2. Diagnosis code-table entries should be preserved as diagnosis signals, not as
   request routes.
3. Omit diagnosis-exclusion ICD tables from the primary artifact unless they are
   needed to define a request-level routing outcome.

## `request_routes`

### Purpose

A request route is the first runtime unit resolved from the billing code.

Each route:

```json
{
  "route_id": "string",
  "label": "string",
  "coverage_status": "covered | not_covered | investigational",
  "terminal_disposition": "continue | stop_not_covered | stop_investigational",
  "billing_codes": ["string"],
  "route_kind": "covered_request | excluded_request | investigational_request | UNKNOWN",
  "phase_prompt_required": true,
  "phase_branches": [
    {
      "phase": "initial | continuation | other",
      "is_default": true,
      "route_guard_ids": ["string"],
      "cluster_ids": ["string"]
    }
  ],
  "routing_notes": "string or UNKNOWN",
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. Billing code is the primary route resolver.
2. A route represents one policy-defined request family, not one billing code.
3. If the policy groups multiple covered billing codes under the same narrative
   criteria, keep them in one shared route with a multi-code `billing_codes`
   array.
4. Separate routes are appropriate only when the policy text gives different
   clinical logic, different terminal coverage outcomes, or clearly distinct
   request families.
5. If a billing code is explicitly not covered or investigational in the code
   table or narrative policy text, create a terminal route.
6. Terminal routes should have:
   - `coverage_status = not_covered` or `investigational`
   - `terminal_disposition = stop_not_covered` or `stop_investigational`
   - empty `cluster_ids` in all phase branches
7. If the policy does not define phase-specific logic, create exactly one phase
   branch:
   - `phase = other`
   - `is_default = true`
   - `phase_prompt_required = false`
8. If the policy defines different logic for initial and continuation, create
   distinct phase branches.
9. If phase-specific cluster logic differs, do not reuse the same cluster ID
   across phases.

## `route_guards`

### Purpose

Clinical-only guards that must be asked after route resolution and before
condition cluster selection.

Examples:

- request is not for diagnosis of COPD
- route applies only to non-ocular use
- route requires a combination drug across the entire route phase

Each guard:

```json
{
  "guard_id": "string",
  "label": "string",
  "guard_type": "exclusion | limitation | safety | coverage_gate | UNKNOWN",
  "applies_to_route_ids": ["string"],
  "applies_to_phases": ["initial | continuation | other"],
  "ask_timing": "before_cluster_selection",
  "logic_root": {},
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. Route guards must be patient clinical guards only.
2. Do not place administrative rules here:
   - precertification
   - site of care
   - prescriber specialty
   - provider network
   - benefit or membership validation
3. Use route guards only when the guard truly applies before cluster selection.
4. If a guard is cluster-specific, do not place it here.

## `cluster_entry_guards`

### Purpose

Clinical guards asked after the clinician selects a cluster, but before the full
 cluster criteria are shown.

Examples:

- prior full IV rituximab dose required before Hycela
- no concomitant biologic rule that applies only to RA or MS branches
- continuation-specific safety gate for one selected disease branch

Each guard:

```json
{
  "guard_id": "string",
  "label": "string",
  "guard_type": "exclusion | limitation | safety | coverage_gate | UNKNOWN",
  "applies_to_route_ids": ["string"],
  "applies_to_phases": ["initial | continuation | other"],
  "applies_to_cluster_ids": ["string"],
  "ask_timing": "after_cluster_selection",
  "logic_root": {},
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. Use cluster-entry guards when the guard should not be shown for every cluster
   in the same route.
2. Cluster-entry guards may be phase-specific.
3. Do not duplicate cluster-entry guards inside cluster `logic_root`.

## `condition_clusters`

### Purpose

Condition clusters are the clinician-selectable intended-to-treat branches under
one route and one phase.

Each cluster:

```json
{
  "cluster_id": "string",
  "route_id": "string",
  "phase": "initial | continuation | other",
  "condition_key": "string",
  "condition_label": "string",
  "condition_synonyms": ["string"],
  "diagnosis_basis": "code_table_primary | narrative_primary | mixed",
  "diagnosis_code_candidates": ["string"],
  "inherits_diagnosis_from_cluster_ids": ["string"],
  "cluster_entry_guard_ids": ["string"],
  "logic_profile_id": "string or UNKNOWN",
  "logic_root": {},
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. One cluster should equal one clinician-selectable intended-to-treat
   diagnosis or one clearly distinct clinical scenario.
2. Clusters are phase-scoped. If continuation logic differs from initial logic,
   emit separate clusters.
3. Prefer code-table diagnosis groupings over narrative disease examples when
   code-table inclusion diagnoses are present.
4. If a narrative disease example is subsumed by a covered code-table range,
   keep it within the code-table-backed cluster rather than creating a separate
   cluster.
5. Do not place administrative logic in clusters.
6. Use `inherits_diagnosis_from_cluster_ids` when a continuation cluster should
   inherit diagnosis scope from one or more initial clusters rather than repeat
   the same diagnosis code lists.
7. When multiple continuation diseases share the same continuation logic, keep
   separate continuation clusters for each clinician-selectable disease and
   reuse a shared `logic_profile_id` instead of collapsing them into one grouped
   continuation cluster.
8. Use `logic_profile_id` when multiple clusters share the same logical rule
   pattern.
9. If diagnosis confirmation is clinically required, the cluster's effective logic must still include diagnosis-grounded evidence, either through inline `logic_root` or a referenced `logic_profile`.
10. `condition_clusters` define scope and should not independently decide standalone-versus-composite criterion decomposition; that decision belongs in `criteria_catalog`.
11. Do not leave a diagnosis-defined cluster with empty effective logic.

## `logic_profiles`

### Purpose

Reusable logic definitions for repeated cluster logic, especially common
continuation rules.

Each logic profile:

```json
{
  "logic_profile_id": "string",
  "label": "string",
  "logic_root": {},
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. Use logic profiles only when the same rule pattern is genuinely reused.
2. Logic profiles are for reuse, not for hiding clinically important
   disease-specific distinctions.
3. When `logic_profile_id` is populated on a cluster, downstream consumers
   should resolve cluster logic from that profile unless an inline `logic_root`
   is also explicitly provided.
4. Logic profiles may centralize repeated continuation logic, but they should
   not remove diagnosis criteria entirely from diagnosis-defined clusters.

## `criteria_catalog`

### Purpose

Atomic clinical facts used by route guards, cluster-entry guards, and cluster
 logic.

Each criterion:

```json
{
  "criterion_id": "string",
  "criterion_kind": "route_guard | cluster_entry_guard | cluster_criterion",
  "prompt": "string",
  "clinical_intent": "string or UNKNOWN",
  "answer_type": "boolean | categorical | numeric | text",
  "required": true,
  "code_binding": {
    "source_codes": ["string"],
    "code_role": "request | diagnosis_inclusion | UNKNOWN"
  },
  "preferred_data_domains": [
    "condition | medication | observation | procedure | document | UNKNOWN"
  ],
  "policy_time_language": "string or UNKNOWN",
  "retrieval_priority": "high | medium | low | UNKNOWN",
  "prefill_allowed": true,
  "clinician_must_confirm": true,
  "evidence": "verbatim text",
  "locator": {
    "section_path": ["string"],
    "page_start": 0,
    "page_end": 0
  }
}
```

Rules:

1. The parser must define what must be proven, not how to query the EHR.
2. Do not emit `execution_hints`, `ehr_query_fragment`, or normalized
   `time_constraint` here.
3. Preserve retrieval-relevant semantic hints only:
   - `code_binding`
   - `preferred_data_domains`
   - `policy_time_language`
4. All criteria should remain clinician-readable.
5. Every diagnosis-dependent cluster must include at least one diagnosis-grounded criterion in its effective logic, but that criterion does not need to be a standalone diagnosis-only criterion.
6. `criteria_catalog` owns whether diagnosis confirmation and qualifier language should stay together as one composite criterion or be split into separate criteria.

## Criterion Decomposition Rules

1. Use the policy clause structure to decide whether one integrated clinical phrase should remain one composite criterion or be split into multiple independent criteria.
2. If a single phrase combines diagnosis with activity, severity, remission, stage, refractory state, progression, or response, prefer one composite criterion unless the policy text separately states independent requirements.
3. If two candidate criteria would cite the same single evidence sentence and create an artificial diagnosis-plus-qualifier split, merge them.
4. A code-table-backed cluster does not automatically require a standalone diagnosis-only criterion.

## `logic_root`

Use a simple boolean tree with references to atomic criteria.

Supported shape:

```json
{
  "node_type": "group",
  "operator": "all | any | none | at_least:n",
  "children": [
    {
      "node_type": "criterion_ref",
      "criterion_id": "CR_EXAMPLE"
    }
  ]
}
```

Rules:

1. `route_guards`, `cluster_entry_guards`, and `condition_clusters` each use
   `logic_root`.
2. Keep logic trees simple and clinically meaningful.

## `locator`

Use structured semantic locators:

```json
{
  "section_path": [
    "I. Criteria for Initial Approval",
    "A. Ampullary adenocarcinoma"
  ],
  "page_start": 3,
  "page_end": 3
}
```

Rules:

- `section_path` is primary
- page numbers are supporting metadata
- use the deepest stable policy header path available

## Artifact 2: route_index_v4 (Derived)

### Purpose

Small deterministic router for the webapp.

This is a derived routing view built from `policy_master_v4`, not a second
canonical parser-authored artifact.

### Top-level fields

- `policy_id`
- `routes`

Each route entry:

```json
{
  "route_id": "string",
  "label": "string",
  "coverage_status": "covered | not_covered | investigational",
  "terminal_disposition": "continue | stop_not_covered | stop_investigational",
  "billing_codes": ["string"],
  "phase_prompt_required": true,
  "phases": [
    {
      "phase": "initial | continuation | other",
      "is_default": true,
      "route_guard_ids": ["string"],
      "cluster_summaries": [
        {
          "cluster_id": "string",
          "condition_key": "string",
          "condition_label": "string",
          "condition_synonyms": ["string"],
          "diagnosis_basis": "code_table_primary | narrative_primary | mixed",
          "diagnosis_code_candidates": ["string"],
          "cluster_entry_guard_ids": ["string"]
        }
      ]
    }
  ],
  "ui_label": "string"
}
```

### Runtime interpretation

1. Derive `route_index_v4` directly from `policy_master_v4`.
2. Resolve route from billing code.
3. If `terminal_disposition` is not `continue`, stop immediately.
4. Prompt for phase only if `phase_prompt_required = true`.
5. Ask only route guards for the selected phase.
6. Show the cluster shortlist for the selected phase, using inherited diagnosis
   scope when applicable.
7. After clinician selects a cluster, ask only that cluster's
   `cluster_entry_guard_ids`.
8. Keep route granularity identical to `policy_master_v4.request_routes`.
9. Then materialize the selected cluster criteria and invoke downstream
   retrieval planning.

## Out of Scope For The Parser

The following belong to the downstream retrieval planner, not parser output:

- `execution_hints`
- `ehr_query_fragment`
- normalized `time_constraint`
- tool selection
- SQL versus note versus hybrid retrieval strategy
- fallback search logic
