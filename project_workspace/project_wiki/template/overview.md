<span id="version" style="color: grey; float: right">Version 0.1.0</span><br/>

<div class="alert">
This is a demo only and thus should not be installed on customer instances.
</div>

# Agent Golden Demo In Healthcare: Prior Authorization Agent #

An intelligent prior authorization review experience that helps clinicians assemble, validate, and finalize a submission-ready authorization package. The centerpiece of the demo is a Dataiku Structured Agent that owns Screen 2 review orchestration: it translates scoped policy criteria into retrieval plans, gathers and reasons over chart evidence, prepares a clinician review payload, and returns a reviewed artifact for deterministic downstream packaging. In the current deployment, the standard webapp and the Structured Agent run in the same DSS project context (`DEMO_PRIOR_AUTH_AGENT`).

## Industry Challenge

Prior authorization remains one of the most resource-intensive administrative workflows in healthcare delivery. Providers must gather clinical evidence, interpret payer-specific policy criteria, identify missing documentation, and prepare a complete submission package under tight operational timelines.

This burden is amplified by the fragmented U.S. payer landscape, where regional and national health plans maintain different coverage rules, evidence expectations, and review processes. The result is repeated manual work, avoidable denials, delayed treatment, and significant clinician and staff frustration.

The core challenge is not making the medical decision itself. It is organizing the required evidence, mapping it to payer policy criteria, surfacing documentation gaps, and producing a compliant package that a human reviewer can trust.

## Golden Demo Highlights

The **Prior Authorization Review Agent** demonstrates a three-screen clinician workflow:

- Screen 1 captures the prior authorization scope through deterministic selection of patient, policy, billing code, phase, cluster, and routing questions.
- Screen 2 is owned by the Structured Agent, which plans retrieval, executes criterion-level reasoning, evaluates policy logic, and prepares the clinician review experience.
- Screen 3 produces a deterministic, submission-ready package derived from the reviewed Screen 2 artifact.

Through this experience, the demo shows how a clinician or prior-auth operations user can:

- identify the relevant prior authorization scope quickly
- review structured eligibility criteria alongside agent-prepared supporting evidence
- inspect and edit unmet or uncertain criteria with a human-in-the-loop checkpoint
- generate a consistent final submission package without relying on free-form agent output for the last mile

## Who This Demo Is For

This demo is primarily framed around the **provider / clinician** workflow, where the user needs to prepare a high-quality authorization request with less manual effort and less back-and-forth.

It also supports broader business conversations with:

- revenue cycle management and clearinghouse teams that want to reduce technical denials and improve first-pass quality
- payer stakeholders interested in more structured, auditable, and review-ready submissions

## Demo Value Proposition

The Prior Authorization Review Agent helps organizations:

- reduce administrative preparation time for prior authorization requests
- improve submission completeness and evidence quality
- shorten time-to-treatment by accelerating preparation and review
- support more consistent human review with a structured checklist
- maintain clearer auditability across evidence retrieval, review, and final package generation
- showcase a Structured Agent pattern for healthcare workflows that separates deterministic scoping, governed reasoning, and deterministic final packaging
- showcase a scalable FHIR-native data foundation for EHR ingestion, evidence retrieval, and future e-prior-auth interoperability
- demonstrate a semantic-model-driven retrieval approach that improves agent transparency, reuse, and governance

## What the Agent Does

Within the current POC scope, the system:

- retrieves the relevant policy context for a selected patient and requested service
- converts policy requirements into a structured review experience
- maps available patient evidence to individual eligibility criteria
- identifies criteria that need confirmation, edits, or additional clinician input
- pauses for explicit human review when running through the Structured Agent
- generates the final Screen 3 package deterministically after review is complete

The agent does **not** make the final coverage decision. It supports evidence assembly, validation, and packaging for a human-led prior authorization workflow.

## Why Dataiku Matters In This Demo

Dataiku provides more than orchestration for the final review workflow. In this demo, it also represents the platform layer for:

- scalable FHIR-aware EHR ETL using PySpark recipes
- use of the Pathling package for FHIR-native data access and transformation
- governed preparation of structured and unstructured healthcare evidence
- a semantic-model-driven retrieval layer that maps policy criteria to the right EHR evidence domain
- operationalizing the Structured Agent with a human-in-the-loop checkpoint
- extending the same architecture toward FHIR API-based ingestion and e-prior-auth submission patterns

## How to Use

Users interact with the Prior Authorization Review webapp through a guided three-screen flow. The webapp demonstrates live Structured Agent execution and human approval.

No installation guidance is included in this wiki chapter because this page is intended to describe the business-facing demo asset rather than deployment steps.
