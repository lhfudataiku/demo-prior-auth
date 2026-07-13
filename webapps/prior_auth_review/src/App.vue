<script setup lang="ts">
import { computed, onMounted } from 'vue'
import PatientSummary from './components/PatientSummary.vue'
import ReviewerNoteCard from './components/ReviewerNoteCard.vue'
import Screen1Page from './components/Screen1Page.vue'
import Screen2Page from './components/Screen2Page.vue'
import Screen3Page from './components/Screen3Page.vue'
import ScopeSummary from './components/ScopeSummary.vue'
import WorkflowNav from './components/WorkflowNav.vue'
import { usePriorAuthStore } from './stores/priorAuthStore'

const store = usePriorAuthStore()

const screenTitle = computed(() => {
  if (store.currentPage === 'screen1') return 'Prior authorization requirement review'
  if (store.currentPage === 'screen2') return 'Clinical eligibility review'
  return 'Final submission review'
})

onMounted(() => {
  void store.initialize()
})
</script>

<template>
  <div class="min-h-screen bg-background text-foreground lg:grid lg:grid-cols-[320px_minmax(0,1fr)]">
    <aside class="border-b border-sidebar-border bg-sidebar px-5 py-6 text-sidebar-foreground lg:min-h-screen lg:border-b-0 lg:border-r">
      <div class="flex flex-col gap-6">
        <div class="space-y-2">
          <p class="font-mono text-xs uppercase tracking-[0.08em] text-sidebar-foreground/70">Prior auth</p>
          <h1 class="font-serif text-4xl font-semibold text-sidebar-foreground">Structured review</h1>
          <p class="max-w-sm text-sm text-sidebar-foreground/78">
            Deterministic scope selection, live clinical review, and auditable submission packaging.
          </p>
        </div>

        <div class="grid gap-4">
          <PatientSummary :patient="store.displayedPatientSummary" :subject-id="store.subjectIdInput" />

          <ScopeSummary
            :policy-id="store.currentScenario?.policy_id ?? null"
            :policy-label="store.currentScenario?.label ?? null"
            :review-scope="store.policyReviewScope"
          />

          <ReviewerNoteCard
            :review-metadata="store.reviewMetadata"
            @update-reviewer="(value) => store.updateReviewMetadata({ reviewer: value })"
            @update-comment="(value) => store.updateReviewMetadata({ comment: value })"
          />
        </div>
      </div>
    </aside>

    <main class="min-w-0 bg-background">
      <div class="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-6 lg:px-8">
        <header class="mb-6 flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
          <div class="space-y-2">
            <p class="font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">Workspace</p>
            <h2 class="font-serif text-3xl font-semibold text-foreground lg:text-4xl">{{ screenTitle }}</h2>
          </div>
        </header>

        <div v-if="store.error" class="mb-6 rounded-2xl border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {{ store.error }}
        </div>

        <WorkflowNav
          :current-page="store.currentPage"
          :screen2-ready="store.isReadyForScreen2"
          :screen3-ready="!!store.latestScreen3 && !store.submitting"
          @navigate="store.goToPage"
        />

        <Screen1Page
          v-if="store.currentPage === 'screen1'"
          :screen1="store.screen1State"
          :loading="store.loading || store.screen2Loading"
          :screen1-answers="store.screen1Answers"
          :scenarios="store.scenarios"
          :selected-policy-id="store.selectedPolicyId"
          :subject-id-input="store.subjectIdInput"
          @select-policy="(policyId) => store.loadScenario(policyId)"
          @update-subject-id="store.updateSubjectIdInput"
          @select-billing-code="(billingCode) => store.advanceScreen1({ billing_code: billingCode, selected_phase: null, selected_cluster_id: null })"
          @select-phase="(phase) => store.advanceScreen1({ selected_phase: phase, selected_cluster_id: null })"
          @select-cluster="(clusterId) => store.advanceScreen1({ selected_cluster_id: clusterId })"
          @answer-guard="store.updateScreen1Answer"
          @proceed="store.openScreen2"
        />

        <Screen2Page
          v-else-if="store.currentPage === 'screen2'"
          :screen2="store.screen2"
          :criteria="store.criteria"
          :criteria-count="store.criteriaCount"
          :edited-answers="store.editedAnswers"
          :logic-evaluation="store.logicEvaluation"
          :answer-origins="store.answerOrigins"
          :submitting="store.submitting"
          :data-source="store.dataSource"
          :agent-status="store.agentStatus"
          :agent-message="store.agentMessage"
          :agent-events="store.agentEvents"
          :agent-progress="store.agentProgress"
          :focused-criterion-id="store.focusedCriterionId"
          @answer="(criterionId, value) => store.updateAnswer(criterionId, { answer: value })"
          @comment="(criterionId, value) => store.updateAnswer(criterionId, { comment: value })"
          @clear-focus="store.clearFocusedCriterion"
          @submit="store.submitReview"
        />

        <Screen3Page
          v-else
          :review-result="store.latestReviewResult"
          :screen3="store.latestScreen3"
          @jump-to-criterion="store.returnToCriterion"
        />
      </div>
    </main>
  </div>
</template>
