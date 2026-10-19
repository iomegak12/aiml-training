// Home page content, based on the project README.

export const HERO = {
  eyebrow: 'Powered by LangChain Deep Agents + OpenAI GPT-5.1',
  title: 'IT support that',
  highlight: 'thinks, plans and acts',
  subtitle:
    'Corvana Networks pairs an AI support assistant with a real ticket desk. Ask in plain English: it raises, finds, updates, resolves and archives tickets, and checks your location, weather and time along the way.',
}

export const FEATURES = [
  {
    icon: 'ticket',
    title: 'Complete ticket lifecycle',
    text: 'Register, search, update, resolve and archive IT tickets stored in SQLite, validated with Pydantic before every change.',
  },
  {
    icon: 'list',
    title: 'Plan → approve → execute',
    text: 'For bigger requests the agent proposes a step-by-step plan first. Nothing runs until you approve it, or ask for changes.',
  },
  {
    icon: 'zap',
    title: 'Live streaming answers',
    text: "Watch the assistant work in real time: its reasoning, every tool it uses, and the answer as it's written (Server-Sent Events).",
  },
  {
    icon: 'chat',
    title: 'Conversation memory',
    text: 'Follow-ups like "move it to In Progress" just work: each conversation keeps its context through a thread ID.',
  },
  {
    icon: 'shield',
    title: 'Built-in guardrails',
    text: 'Per-client rate limiting (100 requests/minute, then a 30-second pause) and structured RFC 9457 errors with request IDs.',
  },
  {
    icon: 'activity',
    title: 'Observable by design',
    text: 'Every request is logged as JSON with its request ID, duration and outcome, plus health and readiness probes.',
  },
]

export const FLOW = [
  { icon: 'globe', title: 'Web app', text: 'React UI served by nginx on port 80' },
  { icon: 'server', title: 'REST API', text: 'FastAPI: chat, streaming, decisions' },
  { icon: 'sparkles', title: 'Deep Agent', text: 'OpenAI GPT-5.1 with high reasoning effort' },
  { icon: 'wrench', title: 'Tools', text: 'Ticket tools + location, weather, time' },
  { icon: 'database', title: 'Ticket desk', text: 'SQLite via SQLAlchemy ORM' },
]

export const TOOLS = {
  tickets: ['register_ticket', 'find_tickets', 'get_ticket', 'update_ticket', 'resolve_ticket', 'archive_ticket'],
  local: ['get_location', 'get_weather', 'get_current_time'],
}

export const LIFECYCLE = ['Open', 'In Progress', 'Resolved', 'Archived']

export const ENDPOINTS = [
  { method: 'POST', path: '/chat', text: 'Complete reply, or a plan to approve in plan mode' },
  { method: 'POST', path: '/chat-streaming', text: 'Live Server-Sent Events: reasoning, tool calls, tokens' },
  { method: 'POST', path: '/chat/decision', text: 'Approve or reject a proposed plan' },
  { method: 'GET', path: '/health', text: 'Liveness probe' },
  { method: 'GET', path: '/ready', text: 'Readiness: settings, API key, database, agents' },
]
