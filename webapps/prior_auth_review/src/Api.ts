import axios from './api/index'

export interface SelectedScope {
  selected_route_id: string
  selected_phase: 'initial' | 'continuation' | 'other'
  selected_cluster_id: string
}

export interface SelectedScopeDisplay {
  route_label: string
  phase_label: string
  cluster_label: string
}

export interface PatientSummary {
  subject_id: string
  gender: string | null
  birth_date: string | null
  age: number | null
}

export interface ReviewMetadata {
  reviewer: string | null
  reviewed_at: string | null
  comment: string | null
}

export interface CriterionAnswer {
  answer: boolean | string | number | null
  value: string | number | null
  comment: string | null
  override_prefill: boolean
}

export type CriterionAnswers = Record<string, CriterionAnswer>

export interface ScenarioOption {
  policy_id: string
  label: string
  description: string
}

export interface RuntimeInfo {
  data_source: 'local' | 'dss'
}

export interface BillingCodeOption {
  billing_code: string
  route_id: string
  route_label: string
  coverage_status: string
}

export interface SelectOption {
  value: string
  label: string
}

export interface ClusterOption {
  cluster_id: string
  cluster_label: string
  condition_key: string | null
  diagnosis_code_candidates: string[]
}

export interface GuardQuestion {
  criterion_id: string
  criterion_kind: 'route_guard' | 'cluster_entry_guard'
  prompt: string
  answer_type: 'boolean' | 'string' | 'number'
  required: boolean
}

export interface SelectedScopeContext {
  policy_id: string
  selected_route_id: string
  selected_route_label: string
  selected_phase: 'initial' | 'continuation' | 'other'
  selected_phase_label: string
  selected_cluster_id: string
  selected_cluster_label: string
  [key: string]: unknown
}

export interface Screen1Payload {
  status: 'ok' | 'blocked' | 'error'
  patient_id_options: string[]
  payload: {
    step: 'collect_billing_code' | 'collect_phase' | 'collect_cluster' | 'review_scope'
    selection: {
      billing_code: string | null
      selected_route_id: string | null
      selected_phase: string | null
      selected_cluster_id: string | null
    }
    billing_code_options: BillingCodeOption[]
    route_display: {
      route_id: string | null
      route_label: string | null
    }
    phase_options: SelectOption[]
    cluster_options: ClusterOption[]
    route_guard_questions: GuardQuestion[]
    cluster_entry_guard_questions: GuardQuestion[]
    selected_scope_context: SelectedScopeContext | null
    criterion_answers: CriterionAnswers
    next_action: 'collect_billing_code' | 'collect_phase' | 'collect_cluster' | 'proceed_screen_2' | 'blocked'
  }
  messages: string[]
  patient_summary: PatientSummary | null
  scenario: ScenarioOption
}

export interface ClinicianInput {
  answer: boolean | string | number | null
  value: string | number | null
  comment: string | null
  override_prefill: boolean
  answered: boolean
}

export interface ChartResult {
  status: 'Found' | 'Missing' | 'Ambiguous' | 'Unreviewed'
  meets_criterion: boolean | null
  extracted_value: Record<string, unknown> | null
  justification: string | null
  sources: {
    structured: Array<Record<string, unknown>>
    notes: Array<Record<string, unknown>>
  }
}

export interface UiResolution {
  display_state: 'satisfied' | 'not_satisfied' | 'needs_clinician' | 'conflict' | 'unanswered'
  prefill_value: boolean | string | number | null
  use_chart_as_prefill: boolean
  conflict_flag: boolean
  conflict_reason: string | null
  final_answer: boolean | string | number | null
  final_source: 'chart' | 'clinician' | 'unresolved'
}

export interface CriterionRow {
  criterion_id: string
  criterion_kind: 'route_guard' | 'cluster_entry_guard' | 'inherited_diagnosis' | 'cluster_criterion'
  prompt: string
  answer_type: 'boolean' | 'string' | 'number'
  required: boolean
  clinician_input: ClinicianInput
  chart_result: ChartResult
  ui_resolution: UiResolution
}

export interface LogicEvaluation {
  selected_cluster_satisfied: boolean
  selected_cluster_status: 'satisfied' | 'not_satisfied' | 'unresolved'
  satisfied_criterion_ids: string[]
  not_satisfied_criterion_ids: string[]
  unresolved_criterion_ids: string[]
  criterion_counts: {
    satisfied: number
    not_satisfied: number
    unresolved: number
  }
}

export interface Screen2Payload {
  status: 'ok' | 'warning' | 'blocked' | 'error'
  payload: {
    selected_scope: SelectedScope
    selected_scope_display?: SelectedScopeDisplay
    criteria: CriterionRow[]
    logic_evaluation: LogicEvaluation
    additional_cluster_suggestions: Array<Record<string, unknown>>
    next_action: 'stay_screen_2' | 'proceed_screen_3'
  }
  messages: string[]
}

export interface Screen2Bootstrap {
  scenario: ScenarioOption
  patient_summary: PatientSummary | null
  screen_2_response: Screen2Payload
}

export interface Screen2RunStart {
  run_id: string
  scenario: ScenarioOption
  patient_summary: PatientSummary | null
}

export interface AgentRunProgress {
  current_block_id: string | null
  current_criterion_id: string | null
  current_criterion_prompt: string | null
  completed_criteria: number
  total_criteria: number | null
}

export interface AgentRunState {
  status: 'running' | 'hitl_paused' | 'completed' | 'failed'
  text_so_far: string
  events: Array<Record<string, unknown>>
  progress: AgentRunProgress | null
  hitl_payload: {
    message?: string
    review_request?: {
      screen_2_payload?: Screen2Payload
      criterion_answers?: CriterionAnswers
    }
  } | null
  screen_2_response: Screen2Payload | null
  screen_3_response: Screen3Payload | null
  edited_answers: CriterionAnswers
  review_result: Screen2ReviewResult | null
  error: string | null
}

export interface Screen2ReviewResult {
  approval_status: 'approved' | 'edited' | 'rejected'
  approved_criterion_answers: CriterionAnswers
  reviewed_screen_2_payload: Screen2Payload
  review_metadata: ReviewMetadata
  human_validated: boolean
}

export interface AnsweredCriterion {
  criterion_id: string
  criterion_kind: string
  prompt: string
  final_answer: boolean | string | number
  final_source: 'chart' | 'clinician' | 'unresolved'
  display_state: string
  comment: string | null
}

export interface Screen3Payload {
  status: 'complete' | 'warning' | 'blocked' | 'error'
  payload: {
    review_summary: {
      selected_scope: SelectedScope
      selected_scope_display?: SelectedScopeDisplay
      criterion_totals: {
        total: number
        answered: number
        unanswered_required: number
        conflicts: number
      }
      logic_evaluation: LogicEvaluation
    }
    answered_criteria: AnsweredCriterion[]
    unanswered_required_items: Array<Record<string, unknown>>
    warnings: string[]
    submission_ready: boolean
  }
  messages: string[]
}

export const Api = {
  async getRuntime() {
    const res = await axios.get<RuntimeInfo>('/api/runtime')
    return res.data
  },

  async listScenarios() {
    const res = await axios.get<{ items: ScenarioOption[] }>('/api/scenarios')
    return res.data.items
  },

  async loadScreen1(policyId: string) {
    const res = await axios.get<Screen1Payload>(`/api/scenarios/${policyId}/screen1/bootstrap`)
    return res.data
  },

  async advanceScreen1(
    policyId: string,
    payload: {
      billing_code?: string | null
      selected_phase?: string | null
      selected_cluster_id?: string | null
      criterion_answers?: CriterionAnswers
    },
  ) {
    const res = await axios.post<Screen1Payload>(`/api/scenarios/${policyId}/screen1/advance`, payload)
    return res.data
  },

  async loadScreen2(
    policyId: string,
    payload: {
      subject_id?: string
      billing_code?: string | null
      selected_phase?: string | null
      selected_cluster_id?: string | null
      criterion_answers?: CriterionAnswers
    },
  ) {
    const res = await axios.post<Screen2Bootstrap>(`/api/scenarios/${policyId}/bootstrap`, payload)
    return res.data
  },

  async loadPatientSummary(subjectId: string) {
    const res = await axios.get<PatientSummary>(`/api/patients/${subjectId}`)
    return res.data
  },

  async startScreen2Run(
    policyId: string,
    payload: {
      subject_id?: string
      billing_code?: string | null
      selected_phase?: string | null
      selected_cluster_id?: string | null
      criterion_answers?: CriterionAnswers
    },
  ) {
    const res = await axios.post<Screen2RunStart>(`/api/scenarios/${policyId}/screen2/run`, payload)
    return res.data
  },

  async getRunState(runId: string) {
    const res = await axios.get<AgentRunState>(`/api/runs/${runId}/state`)
    return res.data
  },

  async respondHitl(
    runId: string,
    approvedCriterionAnswers: CriterionAnswers,
    reviewMetadata?: Partial<ReviewMetadata>,
  ) {
    const res = await axios.post<{ status: 'resuming' }>(`/api/runs/${runId}/hitl/respond`, {
      approved_criterion_answers: approvedCriterionAnswers,
      review_metadata: reviewMetadata ?? {},
    })
    return res.data
  },

  async submitReview(
    policyId: string,
    approvedCriterionAnswers: CriterionAnswers,
    selectionPayload: {
      subject_id?: string
      billing_code?: string | null
      selected_phase?: string | null
      selected_cluster_id?: string | null
      criterion_answers?: CriterionAnswers
    },
    reviewMetadata?: Partial<ReviewMetadata>,
  ) {
    const res = await axios.post<{
      review_result: Screen2ReviewResult
      screen_3_response: Screen3Payload
    }>(`/api/scenarios/${policyId}/review`, {
      ...selectionPayload,
      approved_criterion_answers: approvedCriterionAnswers,
      review_metadata: reviewMetadata ?? {},
    })
    return res.data
  },
}
