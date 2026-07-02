# Prior Auth Assistant — Framework Flowchart

```mermaid
flowchart TD
  subgraph Stores["Dataiku datasets"]
    Tier1["Tier 1: policy_artifacts\npolicy_master_v4 canonical\nroute_index_v4 derived"]
    Tier2["Tier 2: retrieval_plan_cache_v1\nretrieval_plan_v1 by selected scope"]
    SessionDS["Optional: prior_auth_session_state"]
  end

  subgraph Ingestion["Policy ingestion / refresh (offline)"]
    RawPolicy["Raw policy text"] --> Parser["Policy Parser Agent\npolicy_parser_agent_prompt_v4_1.md"]
    Parser --> Builder["route_index_builder.py\nderive route_index_v4"]
    Parser --> Tier1
    Builder --> Tier1
  end

  subgraph Webapp["Clinician webapp"]
    Clinician["Clinician"]
    S1["Screen 1\nRoute + Cluster Selection"]
    S2["Screen 2\nEligibility Review"]
    S3["Screen 3\nFinal Review"]
    Done["Submission-ready summary"]

    Clinician --> S1
    S2 --> S3
    S3 --> Done
  end

  subgraph Backend["Deterministic app/backend"]
    B1["Screen 1 backend\n- load policy_master_v4\n- derive/load route_index_v4\n- run Selection Resolver\n- validate route + cluster-entry guards\n- build scoped_policy_context\n- return initial criterion_answers"]
    CacheLookup{"retrieval_plan_v1 cache hit?"}
  end

  subgraph Orchestrator["Structured Visual Agent"]
    Init["init_state\nstore selected_scope_context\npreserve incoming criterion_answers"]
    Planner["Retrieval Planner Agent\nretrieval_planner_agent_prompt_v1_1.md"]
    PlanReady["retrieval_plan_v1 ready"]
    Exec["FOR_EACH plan_items\nflattened criterion execution"]
    Reasoner["Criterion Reasoning Agent\ncriterion_reasoning_agent_prompt_v1_1.md"]
    Accumulate["accumulate_current_reasoning_result(...)"]
    UIMap["build_criterion_ui_map(...)\nmerge chart results + clinician input\nset conflict_flag"]
    LogicEval["evaluate_logic_tree_from_state(...)"]
    Screen2Payload["prepare_screen_2_review_payload\nbuild_screen2_payload(...)"]
    ReviewTool["request_screen_2_human_review\nmanaged Python tool\nhuman approval enforced"]
    EmitReview["emit screen_2_review_result\nreviewed Screen 2 artifact"]
  end

  subgraph PostReview["Deterministic post-review backend/webapp"]
    CaptureReview["consume screen_2_review_result\nmerge approved edits"]
    Screen3Payload["build_screen3_payload(...)"]
    Emit3["Screen 3 response\nreview_summary + criteria buckets + review_alerts + submission_ready"]
  end

  S1 -->|"screen_1 request / submit:\npolicy_id, subject_id, billing_code,\nselected_phase?, selected_cluster_id?,\nroute guard answers?, cluster-entry guard answers?"| B1
  B1 --> Tier1
  B1 --> S1

  B1 -->|"screen_2 request:\nsubject_id, scoped_policy_context,\noptional initial criterion_answers"| Init
  Init --> CacheLookup
  CacheLookup -->|yes| Tier2
  Tier2 --> PlanReady
  CacheLookup -->|no| Planner
  Planner --> Tier2
  Planner --> PlanReady

  PlanReady --> Exec
  Exec --> Reasoner
  Reasoner --> Accumulate
  Accumulate --> Exec
  Accumulate --> UIMap
  UIMap --> LogicEval
  LogicEval --> Screen2Payload
  Screen2Payload --> ReviewTool
  ReviewTool --> S2

  S2 -->|"human approval:\napprove or edit criterion_answers"| EmitReview
  ReviewTool --> EmitReview
  EmitReview --> CaptureReview
  CaptureReview --> Screen3Payload
  Screen3Payload --> Emit3
  Emit3 --> S3

  B1 --> SessionDS
  EmitReview --> SessionDS
  CaptureReview --> SessionDS
```

Notes:
- Don't overcode. This is a POC.
- `policy_master_v4` is the canonical policy artifact; `route_index_v4` is a deterministic routing view derived from it.
- Screen 1 is deterministic backend logic and owns route resolution, phase selection, cluster selection, and guard collection.
- Screen 1 may return partial clinician answers for selected route guards and cluster-entry guards as initial `criterion_answers`; skipped questions remain unanswered.
- The Structured Visual Agent begins only after scope selection and stores the inner `scoped_policy_context` object as `selected_scope_context`.
- Screen 2 compares chart-backed `criterion_result_map` against clinician input from either Screen 1 or Screen 2 when setting conflict flags in `criterion_ui_map`.
- `criterion_answers` is the working clinician-input map; `approved_criterion_answers` is the approved or submitted snapshot after review.
- Native DSS approval mode uses the managed Python tool as the actual human-review checkpoint.
- Standard webapp review mode uses the same payload shape but collects approved clinician edits directly from the webapp submit flow.
- After approval or submit, the backend/webapp layer deterministically merges approved edits, rebuilds UI state, recomputes logic, and emits the Screen 3 payload.
- POC execution stays flattened: evaluate each criterion once, build `criterion_result_map`, then apply results back to the selected logic tree.
