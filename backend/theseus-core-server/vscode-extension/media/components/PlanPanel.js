export function renderPlanPanel(plan, { panelEl, canReview, onReview, onOpenMarkdown }) {
  if (!panelEl) return;
  panelEl.innerHTML = '';
  const tasks = Array.isArray(plan?.tasks) ? plan.tasks : [];
  if (!tasks.length) {
    panelEl.hidden = true;
    return;
  }

  const header = document.createElement('div');
  header.className = 'plan-header';
  const title = document.createElement('strong');
  title.textContent = 'Plan Tasks';
  const count = document.createElement('span');
  count.textContent = `${tasks.length}`;
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
  actions.append(approve, reject, openMarkdown, jsonToggle);
  header.append(title, count, actions);

  const list = document.createElement('ol');
  list.className = 'plan-task-list';

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

  const jsonTree = document.createElement('pre');
  jsonTree.className = 'plan-json-tree';
  jsonTree.textContent = JSON.stringify(plan, null, 2);
  jsonTree.hidden = true;
  jsonToggle.addEventListener('click', () => {
    jsonTree.hidden = !jsonTree.hidden;
    jsonToggle.classList.toggle('active', !jsonTree.hidden);
  });

  panelEl.append(header, list, jsonTree);
  panelEl.hidden = false;
}
