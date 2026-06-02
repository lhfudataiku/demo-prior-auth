import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  Api,
  type AgentRunState,
  type CriterionAnswer,
  type CriterionAnswers,
  type CriterionRow,
  type PatientSummary,
  type ReviewMetadata,
  type ScenarioOption,
  type Screen1Payload,
  type Screen2ReviewResult,
  type Screen3Payload,
  type Screen2Bootstrap,
  type Screen2Payload,
  type SelectedScopeContext,
} from '../Api'

type WorkflowPage = 'screen1' | 'screen2' | 'screen3'
type AnswerOrigin = 'screen1' | 'screen2'

function cloneAnswers(criteria: CriterionRow[]): CriterionAnswers {
  return criteria.reduce<CriterionAnswers>((acc, criterion) => {
    const input = criterion.clinician_input
    if (input.answered) {
      acc[criterion.criterion_id] = {
        answer: input.answer,
        value: input.value,
        comment: input.comment,
        override_prefill: input.override_prefill,
      }
    }
    return acc
  }, {})
}

function mergeCriterionForPreview(
  criterion: CriterionRow,
  answer?: CriterionAnswer,
): CriterionRow {
  if (!answer) return criterion

  const prefillValue = criterion.ui_resolution.prefill_value
  const hasPrefill = prefillValue !== null && prefillValue !== undefined
  const hasClinicianAnswer = answer.answer !== null && answer.answer !== undefined && answer.answer !== ''
  const conflictFlag = hasClinicianAnswer && hasPrefill && answer.answer !== prefillValue
  const finalAnswer = hasClinicianAnswer ? answer.answer : criterion.ui_resolution.final_answer
  const finalSource = hasClinicianAnswer ? 'clinician' : criterion.ui_resolution.final_source

  let displayState = criterion.ui_resolution.display_state
  if (conflictFlag) {
    displayState = 'conflict'
  } else if (hasClinicianAnswer) {
    displayState = answer.answer ? 'satisfied' : 'not_satisfied'
  }

  return {
    ...criterion,
    clinician_input: {
      answer: answer.answer,
      value: answer.value,
      comment: answer.comment,
      override_prefill: answer.override_prefill,
      answered: hasClinicianAnswer || !!answer.comment,
    },
    ui_resolution: {
      ...criterion.ui_resolution,
      display_state: displayState,
      conflict_flag: conflictFlag,
      conflict_reason: conflictFlag ? 'Clinician answer differs from chart prefill.' : null,
      final_answer: finalAnswer,
      final_source: finalSource,
    },
  }
}

function mergeInitialAnswers(
  screen2: Screen2Payload,
  carriedAnswers: CriterionAnswers,
) {
  const seeded = cloneAnswers(screen2.payload.criteria)
  return {
    ...seeded,
    ...carriedAnswers,
  }
}

function buildAnswerOrigins(
  carriedAnswers: CriterionAnswers,
  criteria: CriterionRow[],
): Record<string, AnswerOrigin> {
  const origins: Record<string, AnswerOrigin> = {}
  for (const criterion of criteria) {
    if (carriedAnswers[criterion.criterion_id]) {
      origins[criterion.criterion_id] = 'screen1'
    } else if (criterion.clinician_input.answered) {
      origins[criterion.criterion_id] = 'screen2'
    }
  }
  return origins
}

function selectedScopeMatchesScreen2(
  selectedScopeContext: SelectedScopeContext | null,
  screen2: Screen2Payload,
) {
  if (!selectedScopeContext) return true
  const selectedScope = screen2.payload.selected_scope
  return (
    selectedScopeContext.selected_route_id === selectedScope.selected_route_id
    && selectedScopeContext.selected_phase === selectedScope.selected_phase
    && selectedScopeContext.selected_cluster_id === selectedScope.selected_cluster_id
  )
}

export const usePriorAuthStore = defineStore('priorAuth', () => {
  const loading = ref(false)
  const screen2Loading = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)

  const scenarios = ref<ScenarioOption[]>([])
  const selectedPolicyId = ref<string>('0059')
  const subjectIdInput = ref('')
  const currentPage = ref<WorkflowPage>('screen1')
  const dataSource = ref<'local' | 'dss'>('local')

  const patientSummary = ref<PatientSummary | null>(null)
  const currentScenario = ref<ScenarioOption | null>(null)

  const screen1State = ref<Screen1Payload | null>(null)
  const screen1Answers = ref<CriterionAnswers>({})

  const screen2Bootstrap = ref<Screen2Bootstrap | null>(null)
  const editedAnswers = ref<CriterionAnswers>({})
  const answerOrigins = ref<Record<string, AnswerOrigin>>({})
  const runId = ref<string | null>(null)
  const agentStatus = ref<'running' | 'hitl_paused' | 'completed' | 'failed' | null>(null)
  const agentEvents = ref<Array<Record<string, unknown>>>([])
  const agentMessage = ref<string | null>(null)
  const agentError = ref<string | null>(null)
  const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

  const reviewMetadata = ref<ReviewMetadata>({
    reviewer: 'POC reviewer',
    reviewed_at: null,
    comment: null,
  })
  const latestReviewResult = ref<Screen2ReviewResult | null>(null)
  const latestScreen3 = ref<Screen3Payload | null>(null)

  const isReadyForScreen2 = computed(
    () => screen1State.value?.payload.next_action === 'proceed_screen_2' && !!screen1State.value?.payload.selected_scope_context,
  )
  const displayedPatientSummary = computed(() => (subjectIdInput.value ? patientSummary.value : null))
  const selectedScopeContext = computed<SelectedScopeContext | null>(
    () => screen1State.value?.payload.selected_scope_context ?? null,
  )
  const policyReviewScope = computed(() => {
    if (screen2.value?.payload.selected_scope_display) {
      return {
        route_label: screen2.value.payload.selected_scope_display.route_label,
        phase_label: screen2.value.payload.selected_scope_display.phase_label,
        cluster_label: screen2.value.payload.selected_scope_display.cluster_label,
        route_id: screen2.value.payload.selected_scope.selected_route_id,
        phase_id: screen2.value.payload.selected_scope.selected_phase,
        cluster_id: screen2.value.payload.selected_scope.selected_cluster_id,
      }
    }
    if (selectedScopeContext.value) {
      return {
        route_label: selectedScopeContext.value.selected_route_label,
        phase_label: selectedScopeContext.value.selected_phase_label,
        cluster_label: selectedScopeContext.value.selected_cluster_label,
        route_id: selectedScopeContext.value.selected_route_id,
        phase_id: selectedScopeContext.value.selected_phase,
        cluster_id: selectedScopeContext.value.selected_cluster_id,
      }
    }
    return null
  })

  const screen2 = computed(() => screen2Bootstrap.value?.screen_2_response ?? null)
  const selectedScope = computed(() => screen2.value?.payload.selected_scope ?? null)
  const selectedScopeDisplay = computed(() => screen2.value?.payload.selected_scope_display ?? null)
  const criteria = computed(() => {
    const current = screen2.value?.payload.criteria ?? []
    return current.map((criterion) =>
      mergeCriterionForPreview(criterion, editedAnswers.value[criterion.criterion_id]),
    )
  })
  const logicEvaluation = computed(() => screen2.value?.payload.logic_evaluation ?? null)
  const nextAction = computed(() => screen2.value?.payload.next_action ?? 'stay_screen_2')

  function currentSelectionPayload() {
    const selection = screen1State.value?.payload.selection
    return {
      subject_id: subjectIdInput.value || undefined,
      billing_code: selection?.billing_code ?? null,
      selected_phase: selection?.selected_phase ?? null,
      selected_cluster_id: selection?.selected_cluster_id ?? null,
      criterion_answers: screen1Answers.value,
    }
  }

  async function initialize() {
    loading.value = true
    error.value = null
    try {
      const runtime = await Api.getRuntime()
      dataSource.value = runtime.data_source
      scenarios.value = await Api.listScenarios()
      await loadScenario(selectedPolicyId.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to load scenarios.'
    } finally {
      loading.value = false
    }
  }

  async function loadScenario(policyId: string) {
    loading.value = true
    error.value = null
    currentPage.value = 'screen1'
    latestReviewResult.value = null
    latestScreen3.value = null
    screen2Bootstrap.value = null
    editedAnswers.value = {}
    answerOrigins.value = {}
    screen1Answers.value = {}
    runId.value = null
    agentStatus.value = null
    agentEvents.value = []
    agentMessage.value = null
    agentError.value = null
    stopPolling()
    try {
      selectedPolicyId.value = policyId
      const screen1 = await Api.loadScreen1(policyId)
      screen1State.value = screen1
      patientSummary.value = subjectIdInput.value ? patientSummary.value : null
      currentScenario.value = screen1.scenario
      reviewMetadata.value = {
        reviewer: 'POC reviewer',
        reviewed_at: null,
        comment: null,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to load scenario.'
    } finally {
      loading.value = false
    }
  }

  function updateScreen1Answer(criterionId: string, answer: boolean | null) {
    const current = screen1Answers.value[criterionId] ?? {
      answer: null,
      value: null,
      comment: null,
      override_prefill: false,
    }
    screen1Answers.value = {
      ...screen1Answers.value,
      [criterionId]: {
        ...current,
        answer,
      },
    }
  }

  async function updateSubjectIdInput(value: string) {
    subjectIdInput.value = value
    if (!value) {
      patientSummary.value = null
      return
    }
    try {
      patientSummary.value = await Api.loadPatientSummary(value)
    } catch {
      patientSummary.value = null
    }
  }

  async function advanceScreen1(patch?: {
    billing_code?: string | null
    selected_phase?: string | null
    selected_cluster_id?: string | null
  }) {
    if (!selectedPolicyId.value || !screen1State.value) return
    loading.value = true
    error.value = null
    try {
      const selection = screen1State.value.payload.selection
      const payload = await Api.advanceScreen1(selectedPolicyId.value, {
        billing_code: patch?.billing_code ?? selection.billing_code,
        selected_phase: patch?.selected_phase ?? selection.selected_phase,
        selected_cluster_id: patch?.selected_cluster_id ?? selection.selected_cluster_id,
        criterion_answers: screen1Answers.value,
      })
      screen1State.value = payload
      patientSummary.value = payload.patient_summary ?? patientSummary.value
      currentScenario.value = payload.scenario
      screen1Answers.value = {
        ...payload.payload.criterion_answers,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to advance Screen 1.'
    } finally {
      loading.value = false
    }
  }

  async function openScreen2() {
    if (!selectedPolicyId.value || !isReadyForScreen2.value) return
    if (!subjectIdInput.value) {
      error.value = 'Enter a patient ID before opening Screen 2.'
      return
    }
    screen2Loading.value = true
    error.value = null
    try {
      if (dataSource.value === 'dss') {
        const run = await Api.startScreen2Run(selectedPolicyId.value, currentSelectionPayload())
        runId.value = run.run_id
        currentScenario.value = run.scenario
        patientSummary.value = run.patient_summary ?? patientSummary.value
        screen2Bootstrap.value = null
        editedAnswers.value = {}
        answerOrigins.value = {}
        agentStatus.value = 'running'
        agentEvents.value = []
        agentMessage.value = null
        agentError.value = null
        currentPage.value = 'screen2'
        startPolling()
        await pollRunState()
        return
      }
      const bootstrap = await Api.loadScreen2(selectedPolicyId.value, currentSelectionPayload())
      if (!selectedScopeMatchesScreen2(screen1State.value?.payload.selected_scope_context ?? null, bootstrap.screen_2_response)) {
        error.value = 'This fixture only has a Screen 2 artifact for one selected scope. Please follow the scenario path shown in Screen 1.'
        return
      }
      screen2Bootstrap.value = bootstrap
      patientSummary.value = bootstrap.patient_summary ?? patientSummary.value
      currentScenario.value = bootstrap.scenario
      editedAnswers.value = mergeInitialAnswers(bootstrap.screen_2_response, screen1Answers.value)
      answerOrigins.value = buildAnswerOrigins(screen1Answers.value, bootstrap.screen_2_response.payload.criteria)
      latestReviewResult.value = null
      latestScreen3.value = null
      currentPage.value = 'screen2'
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to open Screen 2.'
    } finally {
      screen2Loading.value = false
    }
  }

  function goToPage(page: WorkflowPage) {
    if (page === 'screen2' && !screen2.value) return
    if (page === 'screen3' && !latestScreen3.value) return
    currentPage.value = page
  }

  function updateAnswer(criterionId: string, patch: Partial<CriterionAnswer>) {
    const current = editedAnswers.value[criterionId] ?? {
      answer: null,
      value: null,
      comment: null,
      override_prefill: false,
    }
    editedAnswers.value = {
      ...editedAnswers.value,
      [criterionId]: {
        ...current,
        ...patch,
      },
    }
    answerOrigins.value = {
      ...answerOrigins.value,
      [criterionId]: 'screen2',
    }
  }

  function updateReviewMetadata(patch: Partial<ReviewMetadata>) {
    reviewMetadata.value = { ...reviewMetadata.value, ...patch }
  }

  async function submitReview() {
    if (!selectedPolicyId.value) return
    submitting.value = true
    error.value = null
    try {
      if (dataSource.value === 'dss') {
        if (!runId.value) throw new Error('No active agent run.')
        await Api.respondHitl(runId.value, editedAnswers.value, reviewMetadata.value)
        agentStatus.value = 'running'
        agentMessage.value = null
        startPolling()
        await pollRunState()
        return
      }
      const response = await Api.submitReview(
        selectedPolicyId.value,
        editedAnswers.value,
        currentSelectionPayload(),
        reviewMetadata.value,
      )
      latestReviewResult.value = response.review_result
      latestScreen3.value = response.screen_3_response
      currentPage.value = 'screen3'
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to submit review.'
    } finally {
      submitting.value = false
    }
  }

  function stopPolling() {
    if (pollTimer.value) {
      clearInterval(pollTimer.value)
      pollTimer.value = null
    }
  }

  function hydratePausedRun(state: AgentRunState) {
    const screen2Response =
      state.screen_2_response
      ?? state.hitl_payload?.review_request?.screen_2_payload
      ?? null
    if (!screen2Response) return
    screen2Bootstrap.value = {
      scenario: currentScenario.value!,
      patient_summary: patientSummary.value,
      screen_2_response: screen2Response,
    }
    editedAnswers.value = {
      ...(state.hitl_payload?.review_request?.criterion_answers ?? state.edited_answers ?? {}),
    }
    answerOrigins.value = buildAnswerOrigins(screen1Answers.value, screen2Response.payload.criteria)
    agentMessage.value = state.hitl_payload?.message ?? null
  }

  async function pollRunState() {
    if (!runId.value) return
    const state = await Api.getRunState(runId.value)
    agentStatus.value = state.status
    agentEvents.value = state.events ?? []
    agentError.value = state.error ?? null

    if (state.status === 'running') {
      return
    }

    if (state.status === 'hitl_paused') {
      stopPolling()
      hydratePausedRun(state)
      return
    }

    if (state.status === 'completed') {
      stopPolling()
      latestReviewResult.value = state.review_result ?? latestReviewResult.value
      latestScreen3.value = state.screen_3_response ?? latestScreen3.value
      if (latestScreen3.value) {
        currentPage.value = 'screen3'
      }
      return
    }

    if (state.status === 'failed') {
      stopPolling()
      error.value = state.error || 'Agent run failed.'
    }
  }

  function startPolling() {
    stopPolling()
    pollTimer.value = setInterval(() => {
      pollRunState().catch((err) => {
        stopPolling()
        error.value = err instanceof Error ? err.message : 'Unable to poll agent state.'
      })
    }, 2000)
  }

  return {
    agentError,
    agentEvents,
    agentMessage,
    agentStatus,
    answerOrigins,
    criteria,
    currentPage,
    currentScenario,
    displayedPatientSummary,
    editedAnswers,
    error,
    initialize,
    isReadyForScreen2,
    latestReviewResult,
    latestScreen3,
    loadScenario,
    loading,
    logicEvaluation,
    nextAction,
    openScreen2,
    patientSummary,
    policyReviewScope,
    dataSource,
    reviewMetadata,
    screen1Answers,
    screen1State,
    screen2,
    screen2Loading,
    scenarios,
    selectedPolicyId,
    selectedScope,
    selectedScopeContext,
    selectedScopeDisplay,
    submitReview,
    submitting,
    subjectIdInput,
    updateAnswer,
    updateReviewMetadata,
    updateScreen1Answer,
    updateSubjectIdInput,
    advanceScreen1,
    goToPage,
  }
})
