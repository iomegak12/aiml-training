// Messages for the thinking indicator, per phase, mixed with a few good-vibe lines.

export const PHASE_MESSAGES = {
  standard: [
    'Thinking it through…',
    'Reading your request carefully…',
    'Checking the ticket desk…',
    'Putting the answer together…',
  ],
  streaming: [
    'Connecting to the assistant…',
    'Warming up the tools…',
    'Getting the first words ready…',
  ],
  plan: [
    'Mapping out the steps…',
    'Drafting a plan for your approval…',
    'Working out the best order…',
    'Double-checking the plan…',
  ],
  executing: [
    'Running the approved plan…',
    'Working through the steps…',
    'Updating the ticket desk…',
    'Wrapping things up…',
  ],
  revising: [
    'Taking your feedback on board…',
    'Revising the plan…',
    'Reworking the steps…',
  ],
}

export const GOOD_VIBES = [
  'Great things take a moment ✨',
  'Brewing a helpful answer ☕',
  "You're in good hands 🤝",
  'Almost there, hang tight 🚀',
  'Good vibes only while we work 🌈',
  'Turning tickets into solutions 💡',
]

export const PHASE_TITLES = {
  standard: 'Thinking',
  streaming: 'Thinking',
  plan: 'Planning',
  executing: 'Executing plan',
  revising: 'Revising plan',
}

/** Alternate phase messages with good-vibe lines: phase, phase, vibe, phase, phase, vibe… */
export function rotationFor(phase) {
  const steps = PHASE_MESSAGES[phase] || PHASE_MESSAGES.standard
  const sequence = []
  steps.forEach((step, index) => {
    sequence.push(step)
    if (index % 2 === 1) sequence.push(GOOD_VIBES[(index >> 1) % GOOD_VIBES.length])
  })
  sequence.push(GOOD_VIBES[(steps.length + 1) % GOOD_VIBES.length])
  return sequence
}
