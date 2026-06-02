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
  if (store.currentPage === 'screen1') return 'Prior authorization scope review'
  if (store.currentPage === 'screen2') return 'Clinical criterion review'
  return 'Final review summary'
})

onMounted(() => {
  void store.initialize()
})
</script>

<template>
  <div class="app-shell app-shell--workflow">
    <aside class="sidebar">
      <div class="brand-block">
        <p class="eyebrow">Prior auth</p>
        <h1>Structured review</h1>
      </div>

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
    </aside>

    <main class="main-content">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">Workspace</p>
          <h2>{{ screenTitle }}</h2>
          <p class="hero-copy" v-if="store.currentScenario">{{ store.currentScenario.description }}</p>
        </div>
      </header>

      <div v-if="store.error" class="error-banner">{{ store.error }}</div>

      <WorkflowNav
        :current-page="store.currentPage"
        :screen2-ready="store.isReadyForScreen2"
        :screen3-ready="!!store.latestScreen3"
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
        :edited-answers="store.editedAnswers"
        :logic-evaluation="store.logicEvaluation"
        :next-action="store.nextAction"
        :answer-origins="store.answerOrigins"
        :submitting="store.submitting"
        :data-source="store.dataSource"
        :agent-status="store.agentStatus"
        :agent-message="store.agentMessage"
        :agent-events="store.agentEvents"
        :agent-progress="store.agentProgress"
        @answer="(criterionId, value) => store.updateAnswer(criterionId, { answer: value })"
        @comment="(criterionId, value) => store.updateAnswer(criterionId, { comment: value })"
        @submit="store.submitReview"
      />

      <Screen3Page
        v-else
        :review-result="store.latestReviewResult"
        :screen3="store.latestScreen3"
      />
    </main>
  </div>
</template>
