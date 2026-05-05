# Prior Auth Assistant — Framework Flowchart

```mermaid
flowchart TD
  %% =========================
  %% Data Stores
  %% =========================
  subgraph Stores["Dataiku datasets"]
    Tier1["Tier 1: policy_artifacts\n(policy_master_v4 + route_index_v4)"]
    Tier2["Tier 2: retrieval_plan_cache_v1\n(retrieval_plan_v1)"]
    SessionDS["Optional: prior_auth_session_state"]
  end

  %% =========================
  %% Ingestion / Canonical Tier
  %% =========================
  subgraph Ingestion["Policy ingestion / refresh (offline)"]
    RawPolicy["Raw policy text"] --> Parser["Policy Parser Agent\n(policy_parser_agent_prompt_v4.md)"]
    Parser --> Tier1
  end

  %% =========================
  %% Runtime Session (Webapp)
  %% =========================
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

  %% =========================
  %% Deterministic app/backend
  %% =========================
  subgraph Backend["Deterministic app/backend"]
    B1["Screen 1 backend\n- load policy artifacts\n- call Selection Resolver\n- validate route guards\n- validate cluster-entry guards\n- build scoped_policy_context"]
    CacheLookup{"Tier 2 cache hit?"}
  end

  %% =========================
  %% Backend Orchestrator
  %% =========================
  subgraph Orchestrator["Structured Visual Agent (session orchestrator)"]
    Planner["Retrieval Planner Agent\n(retrieval_planner_agent_prompt_v1.md)\n(input: scoped_policy_context)"]
    PlanLoaded["retrieval_plan_v1 ready"]

    Exec["Cluster Executor\n(selected route / phase / cluster only)"]
    Reasoner["Criterion Reasoning Agent\n(atomic criterion adjudication)"]
    O2Resp["Screen 2 response\n- prefills\n- unresolved items\n- chart conflicts\n- optional extra cluster suggestions"]

    O2Submit["Screen 2 submit handler\n- merge clinician answers\n- recompute completeness\n- flag chart conflicts"]
    O3Resp["Screen 3 response\n- answered criteria\n- chart-backed evidence\n- missing required items\n- deviation warnings"]
  end

  %% =========================
  %% Screen 1 request / response
  %% =========================
  S1 -->|"screen_1 request / submit:\npolicy_id, subject_id,\nbilling_code, selected_phase?,\nselected_cluster_id?, guard answers"| B1
  B1 --> Tier1
  B1 --> S1

  %% =========================
  %% Screen 1 handoff to agent layer
  %% =========================
  B1 --> CacheLookup
  CacheLookup -->|yes| Tier2
  Tier2 --> PlanLoaded
  CacheLookup -->|no| Planner
  Planner --> Tier2
  Planner --> PlanLoaded

  %% =========================
  %% Screen 2 execution
  %% =========================
  PlanLoaded --> Exec
  Exec --> Reasoner
  Reasoner --> Exec
  Exec --> O2Resp
  O2Resp --> S2

  %% =========================
  %% Screen 2 submit / review
  %% =========================
  S2 -->|"screen_2 submit:\ncriterion_answers,\noptional include_additional_cluster_ids"| O2Submit
  O2Submit --> O3Resp
  O3Resp --> S3

  %% =========================
  %% Optional session persistence
  %% =========================
  O1 --> SessionDS
  O1Submit --> SessionDS
  O2Submit --> SessionDS
```

Notes:
- Tier 1 uses the canonical `policy_artifacts` dataset to store `policy_master_v4` and `route_index_v4`.
- Tier 2 uses a deterministic `retrieval_plan_cache_v1` dataset keyed by `policy_id`, `selected_route_id`, `selected_phase`, `selected_cluster_id`, and planner-related version fields.
- The Selection Resolver produces `scoped_policy_context`, which is the minimal input bundle for the retrieval planner.
- Screen 1 is fully deterministic and stays in app/backend code.
- The Structured Visual Agent plays the critical orchestration role from retrieval planning through criterion reasoning and final aggregation.
- The runtime evaluates only the selected route/phase/cluster scope; it does not walk the whole legacy questionnaire tree.
- The optional `prior_auth_session_state` dataset is only needed if the webapp should support resume/reload behavior.
