// Starter prompts shown in an empty chat (like the cards in the reference design).

export const SUGGESTIONS = [
  {
    id: 'ticket',
    icon: 'ticket',
    title: 'Raise a support ticket',
    subtitle: "VPN won't connect",
    prompt:
      "Hi, I'm Priya from Finance. Since this morning my laptop can't connect to the office VPN, and I have a client call at 3 PM. Please raise a High priority ticket for me.",
  },
  {
    id: 'local',
    icon: 'cloud',
    title: 'Weather & local time',
    subtitle: 'Where I am right now',
    prompt: "What's the weather and the local time where I am right now?",
  },
  {
    id: 'plan',
    icon: 'list',
    title: 'Plan a multi-step task',
    subtitle: 'Review the plan first',
    enablePlan: true,
    prompt:
      "Check the weather where I am, list all Critical tickets, and then register a Medium priority ticket for the Admin department, raised by Ramkumar, asking the facilities team to prepare for today's weather.",
  },
]
