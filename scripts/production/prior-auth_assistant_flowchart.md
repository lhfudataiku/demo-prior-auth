# Prior Auth Assistant — Framework Flowchart

```mermaid
flowchart TD
  subgraph Stores["Dataiku datasets"]
    Tier1["Tier 1: policy_artifacts\n(policy_master_v4 canonical + route_index_v4 derived)"]
    Tier2["Tier 2: retrieval_plan_cache_v1\n(retrieval_plan_v1)"]
    SessionDS["Optional: prior_auth_session_state"]
  end

  subgraph Ingestion["Policy ingestion / refresh (offline)"]
    RawPolicy["Raw policy text"] --> Parser["Policy Parser Agent\n(policy_parser_agent_prompt_v4.md)"]
    Parser --> Builder["route_index_builder.py\n(derive route_index_v4)"]
    Parser --> Tier1
    Builder --> Tier1
  end

  subgraph Webapp["Webapp (clinician-facing)"]
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
    B1["Screen 1 backend\n- load policy_master_v4\n- derive/load route_index_v4\n- run Selection Resolver\n- validate route + cluster-entry guards\n- build scoped_policy_context"]
    CacheLookup{"Tier 2 cache hit?"}
  end

  subgraph Orchestrator["Structured Visual Agent"]
    Planner["Retrieval Planner Agent\n(retrieval_planner_agent_prompt_v1.md)\n(input: scoped_policy_context)"]
    PlanLoaded["retrieval_plan_v1 ready"]

    Exec["Flattened criterion executor\n(loop over plan_items)"]
    Reasoner["Criterion Reasoning Agent\n(atomic criterion adjudication)"]
    ResultMap["criterion_result_map\n(one result per criterion_id)"]
    LogicEval["Logic Tree Evaluator\n(apply result map to selected cluster logic tree)"]
    O2Resp["Screen 2 response\n- prefills\n- unresolved items\n- chart conflicts\n- logic evaluation\n- optional extra cluster suggestions"]

    O2Submit["Screen 2 submit handler\n- merge clinician answers\n- recompute completeness\n- flag chart conflicts"]
    O3Resp["Screen 3 response\n- answered criteria\n- chart-backed evidence\n- missing required items\n- deviation warnings"]
  end

  S1 -->|"screen_1 request / submit:\npolicy_id, subject_id,\nbilling_code, selected_phase?,\nselected_cluster_id?, guard answers"| B1
  B1 --> Tier1
  B1 --> S1

  B1 --> CacheLookup
  CacheLookup -->|yes| Tier2
  Tier2 --> PlanLoaded
  CacheLookup -->|no| Planner
  Planner --> Tier2
  Planner --> PlanLoaded

  PlanLoaded --> Exec
  Exec --> Reasoner
  Reasoner --> Exec
  Exec --> ResultMap
  ResultMap --> LogicEval
  LogicEval --> O2Resp
  O2Resp --> S2

  S2 -->|"screen_2 submit:\ncriterion_answers,\noptional include_additional_cluster_ids"| O2Submit
  O2Submit --> O3Resp
  O3Resp --> S3

  B1 --> SessionDS
  O2Submit --> SessionDS
```

Notes:
- Tier 1 stores canonical `policy_master_v4` plus derived `route_index_v4`.
- Tier 2 stores `retrieval_plan_v1` keyed by selected route, phase, and cluster.
- Screen 1 is deterministic backend logic.
- Screen 1 cluster shortlists should stay disease-specific, including continuation branches.
- The Structured Visual Agent is the critical orchestration layer from retrieval planning through final aggregation.
- POC execution is flattened: evaluate each criterion once, build `criterion_result_map`, then evaluate the selected logic tree.
- Runtime scope is limited to the selected route/phase/cluster; it does not walk the full legacy questionnaire tree.
