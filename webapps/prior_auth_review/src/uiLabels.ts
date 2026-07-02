export function toneForStatus(value: string | null | undefined): string {
  const normalized = (value || '').toLowerCase()

  if ([
    'ok',
    'satisfied',
    'found',
    'approved',
    'positive',
    'complete',
    'completed',
    'yes',
    'ready',
    'proceed_screen_3',
  ].includes(normalized)) return 'positive'

  if ([
    'warning',
    'conflict',
    'ambiguous',
    'not_satisfied',
    'edited',
  ].includes(normalized)) return 'warning'

  if ([
    'failed',
    'error',
    'blocked',
    'rejected',
  ].includes(normalized)) return 'critical'

  if ([
    'needs_clinician',
    'unanswered',
    'unreviewed',
    'unresolved',
    'neutral',
    'missing',
    'running',
    'hitl_paused',
    'stay_screen_2',
  ].includes(normalized)) return 'neutral'

  return normalized || 'neutral'
}

export function labelForNextAction(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    collect_billing_code: 'Select billing code',
    collect_phase: 'Select treatment phase',
    collect_cluster: 'Select diagnosis cluster',
    proceed_screen_2: 'Ready for eligibility review',
    stay_screen_2: 'Continue eligibility review',
    proceed_screen_3: 'Ready for final review',
    blocked: 'Additional input required',
  }
  return labels[value || ''] ?? humanizeToken(value)
}

export function labelForCriterionKind(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    route_guard: 'Route guard',
    cluster_entry_guard: 'Disease cluster entry guard',
    inherited_diagnosis: 'Inherited diagnosis',
    cluster_criterion: 'Cluster criterion',
  }
  return labels[value || ''] ?? humanizeToken(value)
}

export function labelForCriterionState(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    satisfied: 'Satisfied',
    not_satisfied: 'Not satisfied',
    needs_clinician: 'Needs clinician review',
    conflict: 'Conflict',
    unanswered: 'Unanswered',
    unresolved: 'Unresolved',
  }
  return labels[value || ''] ?? humanizeToken(value)
}

export function labelForChartStatus(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    Found: 'Found',
    Missing: 'Missing',
    Ambiguous: 'Ambiguous',
    Unreviewed: 'Unreviewed',
  }
  return labels[value || ''] ?? humanizeToken(value)
}

export function humanizeToken(value: string | null | undefined): string {
  if (!value) return '—'
  return value
    .split('_')
    .join(' ')
    .replace(/\b\w/g, (match: string) => match.toUpperCase())
}
