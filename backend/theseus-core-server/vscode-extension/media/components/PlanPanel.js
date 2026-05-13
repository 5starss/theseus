export function renderPlanPanel(plan, { panelEl, canReview, onReview, onOpenMarkdown, onCancel, onDelete }) {
  if (!panelEl) return;
  panelEl.innerHTML = '';
  const tasks = Array.isArray(plan?.tasks) ? plan.tasks : [];
  const rawPhase = String(plan?.reviewState || plan?.phase || (canReview ? 'review' : '')).toLowerCase();
  const doneStatuses = new Set(['done', 'completed', 'complete', 'skipped', 'cancelled', 'canceled']);
  const isComplete = ['done', 'completed', 'complete'].includes(rawPhase) || (tasks.length > 0 && tasks.every(task => {
    const status = String(task?.status || '').trim().toLowerCase();
    return doneStatuses.has(status);
  }));
  const phase = isComplete ? 'done' : rawPhase;
  if (!tasks.length && !phase) {
    panelEl.hidden = true;
    return;
  }
  const isDrafting = ['draft', 'drafting'].includes(phase);
  const isActivePlan = !isComplete;

  const header = document.createElement('div');
  header.className = 'plan-header';
  const titleGroup = document.createElement('div');
  titleGroup.className = 'plan-title';
  const title = document.createElement('strong');
  title.textContent = 'Plan Tasks';
  const count = document.createElement('span');
  count.className = 'plan-title-count';
  count.textContent = `${tasks.length}`;
  titleGroup.append(title, count);
  const badge = document.createElement('span');
  badge.className = `plan-phase-badge ${phase || 'drafting'}`;
  badge.textContent = isDrafting && !tasks.length ? 'Drafting' : (phase || 'Drafting');
  titleGroup.appendChild(badge);
  const actions = document.createElement('div');
  actions.className = 'plan-actions';
  const approve = document.createElement('button');
  approve.type = 'button';
  approve.textContent = 'Approve';
  approve.disabled = !canReview;
  approve.addEventListener('click', () => onReview('approve'));
  const reject = document.createElement('button');
  reject.type = 'button';
  reject.textContent = 'Reject';
  reject.disabled = !canReview;
  reject.addEventListener('click', () => onReview('reject'));
  const jsonToggle = document.createElement('button');
  jsonToggle.type = 'button';
  jsonToggle.textContent = 'JSON';
  const openMarkdown = document.createElement('button');
  openMarkdown.type = 'button';
  openMarkdown.textContent = 'Open MD';
  openMarkdown.addEventListener('click', () => onOpenMarkdown(plan));
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.textContent = 'Cancel';
  cancel.title = 'Cancel this plan and reset the runner plan state.';
  cancel.addEventListener('click', () => onCancel?.());
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.textContent = 'Delete';
  remove.title = 'Remove this plan from the current session.';
  remove.className = 'danger';
  remove.addEventListener('click', () => onDelete?.());
  if (canReview && !isComplete) actions.append(approve, reject);
  if (isActivePlan) actions.append(cancel);
  actions.append(remove);
  actions.append(openMarkdown, jsonToggle);
  header.append(titleGroup, actions);

  const stepper = document.createElement('div');
  stepper.className = 'plan-stepper';
  const steps = [
    ['drafting', 'Draft'],
    ['wait', 'Review'],
    ['executing', 'Execute'],
    ['verifying', 'Verify'],
    ['done', 'Done'],
  ];
  const phaseMap = {
    draft: 'drafting',
    wait: 'wait',
    waitforreview: 'wait',
    wait_for_review: 'wait',
    review: 'wait',
    approved: 'executing',
    execute: 'executing',
    rejected: 'drafting',
    verify: 'verifying',
    completed: 'done',
    complete: 'done',
  };
  const current = isComplete ? 'done' : (phaseMap[phase] || phase || 'wait');
  const currentIndex = Math.max(0, steps.findIndex(([key]) => key === current));
  steps.forEach(([key, label], index) => {
    const step = document.createElement('span');
    step.className = `plan-step ${index < currentIndex ? 'done' : index === currentIndex ? 'active' : ''}`;
    step.textContent = label;
    stepper.appendChild(step);
  });

  const list = document.createElement('ol');
  list.className = 'plan-task-list';
  if (isComplete) list.classList.add('complete');

  const marks = { done: '✓', running: '…', failed: '!', pending: '○' };
  tasks.forEach(task => {
    const li = document.createElement('li');
    li.className = `plan-task ${task.status || 'pending'}`;

    const mark = document.createElement('span');
    mark.className = 'plan-task-mark';
    mark.textContent = marks[task.status] || marks.pending;

    const body = document.createElement('span');
    body.className = 'plan-task-body';
    const id = task.id ? `[${task.id}] ` : '';
    body.textContent = `${id}${task.title || task.description || 'Untitled task'}`;

    li.append(mark, body);
    list.appendChild(li);
  });
  if (!tasks.length) {
    const empty = document.createElement('li');
    empty.className = 'plan-task drafting';
    const mark = document.createElement('span');
    mark.className = 'plan-task-mark';
    mark.textContent = '…';
    const body = document.createElement('span');
    body.className = 'plan-task-body';
    body.textContent = plan?.pendingTitle
      ? `Planning: ${plan.pendingTitle}`
      : 'Planning is in progress.';
    empty.append(mark, body);
    list.appendChild(empty);
  }

  const jsonTree = document.createElement('pre');
  jsonTree.className = 'plan-json-tree';
  jsonTree.textContent = JSON.stringify(plan, null, 2);
  jsonTree.hidden = true;
  jsonToggle.addEventListener('click', () => {
    jsonTree.hidden = !jsonTree.hidden;
    jsonToggle.classList.toggle('active', !jsonTree.hidden);
  });

  if (isComplete) {
    const summary = document.createElement('details');
    summary.className = 'plan-complete-summary';
    const summaryTitle = document.createElement('summary');
    summaryTitle.textContent = `Done · ${tasks.length} task${tasks.length === 1 ? '' : 's'}`;
    summary.append(summaryTitle, list);
    panelEl.append(header, stepper, summary, jsonTree);
  } else {
    panelEl.append(header, stepper, list, jsonTree);
  }
  panelEl.hidden = false;
}
