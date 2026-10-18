export const VERDICTS = {
  SUPPORTED: { label: 'Supported', tone: 'green' },
  POTENTIAL_CONTRADICTION: { label: 'Potential contradiction', tone: 'red' },
  POSSIBLY_OUTDATED: { label: 'Possibly outdated', tone: 'amber' },
  INCOMPLETE_INFORMATION: { label: 'Incomplete information', tone: 'blue' },
  INSUFFICIENT_EVIDENCE: { label: 'Insufficient evidence', tone: 'slate' },
}
export const PRIORITIES = {
  critical: { label: 'Critical', tone: 'red' },
  high: { label: 'High', tone: 'orange' },
  medium: { label: 'Medium', tone: 'amber' },
  low: { label: 'Low', tone: 'slate' },
}
export const STATUSES = {
  open: { label: 'Open', tone: 'blue' },
  in_review: { label: 'In review', tone: 'violet' },
  awaiting_correction: { label: 'Awaiting correction', tone: 'amber' },
  resolved: { label: 'Resolved', tone: 'green' },
  dismissed: { label: 'Dismissed', tone: 'slate' },
}
export const DECISIONS = {
  confirm: { label: 'Confirm issue', hint: 'The claim conflicts with the evidence. The site owner must correct the page.' },
  needs_info: { label: 'Needs more information', hint: 'Keep the incident open while you gather context.' },
  dismiss: { label: 'Dismiss as false alarm', hint: 'The claim is acceptable, for example a valid exception.' },
}
