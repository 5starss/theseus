export const SLASH_COMMANDS = [
  { value: '/tools', description: 'Refresh and open Custom Tools', scope: 'local', kind: 'local' },
  { value: '/tools custom', description: 'Show custom tool list', scope: 'local', kind: 'local' },
  { value: '/session', description: 'Open session list', scope: 'local', kind: 'local' },
  { value: '/sessions', description: 'Open session list', scope: 'local', kind: 'local' },
  { value: '/session list', description: 'Refresh session list', scope: 'local', kind: 'local' },
  { value: '/session new', description: 'Create a new session', scope: 'local', kind: 'local' },
  { value: '/session delete', description: 'Delete a session by name', scope: 'local', kind: 'local' },
  { value: '/clear', description: 'Clear visible chat history', scope: 'local', kind: 'local' },
  { value: '/help', description: 'Show command help', scope: 'local', kind: 'local' },
  { value: '/?', description: 'Show command help', scope: 'local', kind: 'local' },
  { value: '/quit', description: 'Stop the runner', scope: 'local', kind: 'local' },
  { value: '/exit', description: 'Stop the runner', scope: 'local', kind: 'local' },
  { value: '/cost', description: 'Show runner token/cost stats', scope: 'runner required', kind: 'runner' },
  { value: '/stats', description: 'Show runner session stats', scope: 'runner required', kind: 'runner' },
  { value: '/validate', description: 'Validate custom tools in runner', scope: 'runner required', kind: 'runner' },
  { value: '/plan approve', description: 'Approve a pending plan', scope: 'plan review only', kind: 'planReview' },
  { value: '/plan reject', description: 'Reject a pending plan', scope: 'plan review only', kind: 'planReview' },
  { value: '/plan cancel', description: 'Cancel the current session plan', scope: 'runner required', kind: 'localPlan' },
  { value: '/plan clear', description: 'Cancel the current session plan', scope: 'runner required', kind: 'localPlan' },
  { value: '/plan delete', description: 'Delete the current session plan', scope: 'runner required', kind: 'localPlan' },
  { value: '/plan remove', description: 'Delete the current session plan', scope: 'runner required', kind: 'localPlan' },
  { value: '/agent', description: 'Use the mode selector to switch modes', scope: 'mode selector', kind: 'mode' },
  { value: '/ask', description: 'Use the mode selector to switch modes', scope: 'mode selector', kind: 'mode' },
  { value: '/plan', description: 'Use the mode selector to switch modes', scope: 'mode selector', kind: 'mode' },
  { value: '/coordinator', description: 'Use the mode selector to switch modes', scope: 'mode selector', kind: 'mode' },
];

export function normalizeSlashCommand(text) {
  return String(text || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

export function findSlashCommand(text) {
  const normalized = normalizeSlashCommand(text);
  return SLASH_COMMANDS.find(command => normalized === command.value || normalized.startsWith(`${command.value} `)) || null;
}

export function slashCommandRemainder(text, commandValue) {
  const raw = String(text || '').trim();
  return raw.slice(commandValue.length).trim();
}
