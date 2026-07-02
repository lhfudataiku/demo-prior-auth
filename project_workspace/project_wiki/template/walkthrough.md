# Case Study

Prior authorization is a high-friction operational step in the healthcare revenue and care delivery workflow. Before a treatment can move forward, provider teams must determine whether authorization is required, gather payer-specific evidence, complete the relevant eligibility checklist, and submit a package that is complete enough to avoid preventable delays or denials.

## Project Background

A provider organization or clinician support team wants to reduce the time spent assembling prior authorization submissions while improving submission quality. The team needs a guided workflow that can combine patient context, payer policy requirements, and clinician review into a single experience.

Beyond the webapp itself, this project also demonstrates how Dataiku can natively support large-scale healthcare data preparation for agentic workflows. The underlying design uses the FHIR community Pathling Python package together with PySpark recipes for EHR ETL, creating a flexible foundation for both evidence retrieval and future FHIR API-based interoperability.

## Initial Situation

Today, many prior authorization workflows are assembled manually across fragmented tools and documentation sources. Staff members often need to:

- interpret policy requirements and coverage criteria
- search for supporting evidence across patient records
- identify which criteria are already met versus which require clarification
- prepare a final package for submission

This process is repetitive, time-sensitive, and vulnerable to missing documentation or inconsistent interpretation.

**Goals**:

- reduce manual administrative work in prior authorization preparation
- improve completeness and consistency of the submission package
- preserve explicit clinician oversight for uncertain or unmet criteria
- propose a flexible and robust structured agent framework, adaptable to various personas and their unique workflows

## Structured Agent Flow

This POC is centered on the Structured Agent that owns Screen 2 after Screen 1 has already resolved the selected route, phase, cluster, and guard answers. In the current DSS deployment, the webapp and the Structured Agent are co-located in project `DEMO_PRIOR_AUTH_AGENT`, and the backend resolves the agent from that active project context.

At a high level, the flow is:

- accept `subject_id` and scoped policy context from the deterministic Screen 1 flow
- load or generate a retrieval plan for the selected criteria
- execute one reasoning pass per criterion to build a chart-backed criterion result map
- evaluate the selected cluster logic tree against the scoped policy context
- prepare a clinician-facing Screen 2 review payload with ordered criteria, evidence, and next action
- pause at the managed human review checkpoint so the clinician can approve or edit the answers
- emit the reviewed Screen 2 artifact for deterministic downstream transformation into Screen 3

![structured_agent.png](9JmM3T4ufiBc)

This design is important because it gives the demo a governed division of labor:

- deterministic backend logic handles Screen 1 scope selection
- the Structured Agent handles Screen 2 retrieval, reasoning, and review preparation
- deterministic backend logic handles Screen 3 generation after clinician-reviewed approval

## Dataiku and FHIR at Scale

An important part of this demo is the data architecture that sits behind the prior authorization review experience.

The project highlights Dataiku's native ability to ingest and process EHR data in FHIR format at scale by combining:

- the Pathling Python package for FHIR-oriented data access and transformation
- PySpark recipes for scalable EHR ETL
- a workflow design that remains compatible with direct FHIR API integrations

This gives the solution flexibility across two important stages of the prior authorization lifecycle:

- upstream EHR ingestion and normalization for evidence retrieval
- downstream e-prior-auth submission patterns that may rely on FHIR APIs

As a result, the demo can be positioned not only as a clinician workflow accelerator, but also as a practical healthcare data and interoperability foundation for production-oriented extensions.

![FHIR_ETL.png](PpsdDbjrVs7g)

## Semantic Model Used by the Agent

Another important feature to highlight in this demo is the semantic model that grounds the agent's retrieval and reasoning behavior.

Instead of treating the EHR as a flat collection of tables or documents, the agent plans its work against a typed healthcare evidence model. The retrieval planner assigns each criterion to a semantic target and retrieval pattern, helping the system stay aligned to the clinical meaning of the policy requirement.

The semantic model organizes evidence around core entities such as:

- patient
- condition
- encounter
- medication and medication request
- observation
- procedure
- imaging
- document

It also uses reusable retrieval archetypes for common evidence tasks, including:

- diagnosis-code confirmation with lookback logic
- medication exposure and treatment-duration checks
- numeric and qualitative observation retrieval
- encounter timing and care-setting checks
- procedure history lookup
- hybrid structured-plus-note retrieval when narrative context is required

This is especially valuable in prior authorization because many criteria are not simple keyword checks. Some require the agent to distinguish between:

- coded diagnosis confirmation
- disease activity, severity, remission, or progression qualifiers
- structured medication history versus narrative treatment intent
- directly observed evidence versus evidence that still requires clinician confirmation

In the current design, the semantic model helps the agent produce a more controlled retrieval plan, query the right structured EHR domain first when appropriate, and invoke semantic clinical-note search when structured evidence alone is insufficient. This improves consistency, transparency, and auditability across policies.

![semantic_model.png](lR3PSsyOKO2z)

## User Journey

The Prior Authorization Review Agent is organized into a three-screen workflow that mirrors the operational steps of preparing a prior authorization request.

### Screen 1: Define the Prior Authorization Scope

The user begins by selecting the scope of the request through a deterministic sequence:

- patient
- policy
- billing code
- phase when required
- cluster selection
- route-guard and cluster-entry-guard questions

This screen establishes the exact context needed for downstream evidence retrieval and policy review. Because the logic is deterministic, it provides a stable and repeatable entry point for the demo.

![webapp_screen1.png](AWHVchYZoBon)
Figure 1 - selecting the scope of prior-auth review

**TEST CASES for demo**
Use case 1: (starter scenario of a simple policy with one routing, one guard question, and one disease criterion)
- patient id: `8e77dd0b-932d-5790-9ba6-5c6df8434457`
- policy id: `0059`
- billing code: `any`
- phase: `other`
- cluster: `obstructive pulmonary conditions`
- route-guard question 1: `Criterion met`

Use case 2: (advanced scenario of a policy of multiple indications, a guard question, and several disease criteria)
- patient id: `a0bcbbc0-b432-5f7d-ac63-28212f20dead`
- policy id: `0655`
- billing code: `any`
- phase: `continuation`
- cluster: `ulcerative colitis`
- route-guard question 1: `Criterion met`

### Screen 2: Review Eligibility Criteria and Evidence

Once the scope is set, the system produces a structured eligibility review experience. This is the central decision-support screen in the demo.

The user can:

- inspect the policy-derived criteria checklist
- review available evidence mapped to each criterion
- see progress and agent feedback
- edit or confirm clinician answers where evidence is incomplete or ambiguous

In the current demo path, the Structured Agent turns the scoped policy context into a retrieval plan, executes criterion-level reasoning, evaluates the logic tree, and prepares the Screen 2 review payload before pausing for clinician review. This screen produces a reviewed, clinician-validated artifact that captures the status of each eligibility criterion.

Under the hood, this step is where the EHR data foundation matters most: the agent workflow depends on structured access to patient evidence that can be prepared from FHIR-based records through Pathling and scalable PySpark ETL patterns in Dataiku.

It is also where the semantic model becomes visible in practice: each eligibility criterion can be mapped to a typed evidence domain and an execution strategy, allowing the agent to move from policy language to a concrete retrieval plan before generating a clinician-facing review result.

![webapp_screen2_1.png](Uhn0oQIg8AXO)
Figure 2.1 - The Structured Agent queries clinical evidence from the patient chart and reasons against the eligibility criteria

![webapp_screen2_2.png](nH73YeTAPZx4)
Figure 2.2 - Snapshot of the agent output from the criterion card and the fields for clinician review

### Screen 3: Review the Final Submission Package

After the Screen 2 review is complete, the system generates Screen 3 deterministically. This is an important part of the current architecture and should be emphasized during the demo.

Rather than letting the Structured Agent generate the final package directly, the backend builds Screen 3 from the reviewed Screen 2 artifact. This provides:

- a more stable final output
- a clearer audit boundary between reasoning and packaging
- flexibility for future downstream targets such as FHIR packaging or other submission formats

The user can review the assembled final package and, if needed, return to a targeted Screen 2 criterion for deterministic re-editing.

![webapp_screen3.png](m45yCkYsdYHh)
Figure 3 - final review before submission

## DSS Human-in-the-Loop Variant

In the DSS runtime, the walkthrough should call attention to the native approval pattern that sits inside the Structured Agent flow:

- a live Structured Agent run is started after Screen 1
- the agent loads or generates a retrieval plan and executes criterion-level reasoning
- progress is streamed into the webapp
- the workflow pauses for human review at the appropriate checkpoint
- the clinician approves or edits the review result
- the system resumes and returns a reviewed Screen 2 artifact
- Screen 3 is then generated deterministically outside the agent

This is a strong proof point for governance, transparency, and controlled operationalization of AI-assisted workflows because the review boundary is explicit and the post-approval output is stable.

## Business Outcomes to Emphasize

During the demo, the strongest business outcomes to highlight are:

- faster preparation of prior authorization submissions
- reduced risk of incomplete documentation
- improved consistency in how policy criteria are reviewed
- lower administrative burden on clinicians and supporting staff
- clearer auditability through structured review artifacts and explicit human approval
- a scalable FHIR-native data foundation that can support both EHR ingestion and future e-prior-auth interoperability
- a semantic-model-driven agent workflow that is more transparent and reusable than ad hoc prompt-only retrieval

## Suggested Demo Talk Track

An effective walkthrough narrative is:

1. Start with the operational burden of prior authorization and the fragmentation of payer rules.
2. Show Screen 1 as the deterministic scoping layer that narrows the request to the right patient, policy, and treatment context.
3. Use Screen 2 to demonstrate how evidence and policy criteria are brought together into a structured human review experience.
4. Pause on the streamed progress and human approval checkpoint to reinforce governance.
5. Finish on Screen 3 by explaining that the final submission package is generated deterministically from the reviewed artifact, which improves reliability and downstream flexibility.
