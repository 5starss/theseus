/*
 * PlanPanel — 상단 패널은 stepper + phase badge + action 버튼 + JSON 토글만.
 * MD 본문은 더 이상 패널에 렌더하지 않고 main.js가 메인 채팅에 별도 메시지로 표시.
 * (planToInlineMarkdown은 외부에서도 사용할 수 있도록 export 유지)
 */

// ── MD 변환 helpers (host측 ChatViewProvider.formatPlanMarkdown 미러) ──

function isRecord(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function planLabel(key) {
  return String(key)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function scalarText(value) {
  if (value === null) return 'null';
  if (value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function withoutUiState(plan) {
  const copy = {};
  for (const [key, value] of Object.entries(plan || {})) {
    if (['reviewState', 'session', 'updatedAt', 'startedAt', 'pendingTitle'].includes(key)) continue;
    copy[key] = value;
  }
  return copy;
}

function planTaskTitle(task, index) {
  const id = task.id ? `[${scalarText(task.id)}] ` : '';
  return `${id}${scalarText(task.title || task.description || `Task ${index + 1}`)}`;
}

function appendMarkdownValue(lines, key, value, level) {
  if (value === undefined) return;
  const heading = '#'.repeat(Math.min(level, 6));
  const label = planLabel(key);

  if (Array.isArray(value)) {
    if (!value.length) return;
    lines.push(`${heading} ${label}`, '');
    for (const [index, item] of value.entries()) {
      if (isRecord(item)) {
        const title = scalarText(
          item.title || item.name || item.description || item.id || `Item ${index + 1}`,
        );
        lines.push(`${'#'.repeat(Math.min(level + 1, 6))} ${title}`, '');
        for (const [childKey, childValue] of Object.entries(item)) {
          if (['title', 'name'].includes(childKey)) continue;
          appendMarkdownValue(lines, childKey, childValue, level + 2);
        }
      } else {
        lines.push(`- ${scalarText(item)}`);
      }
    }
    lines.push('');
    return;
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, childValue]) => childValue !== undefined);
    if (!entries.length) return;
    lines.push(`${heading} ${label}`, '');
    for (const [childKey, childValue] of entries) {
      appendMarkdownValue(lines, childKey, childValue, level + 1);
    }
    return;
  }

  const rendered = scalarText(value).trim();
  if (!rendered) return;
  if (rendered.includes('\n')) {
    lines.push(`${heading} ${label}`, '', rendered, '');
  } else {
    lines.push(`- **${label}**: ${rendered}`);
  }
}

/** 메인 채팅에 표시할 plan MD (Open MD 외부 문서의 축약 버전 — 헤더/JSON dump 제외) */
export function planToInlineMarkdown(plan) {
  const sanitized = withoutUiState(plan || {});
  const tasks = Array.isArray(sanitized.tasks) ? sanitized.tasks : [];
  const lines = [];

  if (plan?.goal || plan?.title) {
    lines.push(`### ${scalarText(plan.goal || plan.title)}`, '');
  }

  if (tasks.length) {
    lines.push('#### Tasks', '');
    for (const [index, task] of tasks.entries()) {
      if (!isRecord(task)) {
        lines.push(`${index + 1}. ${scalarText(task)}`);
        continue;
      }
      const status = task.status ? ` _(${scalarText(task.status)})_` : '';
      lines.push(`${index + 1}. **${planTaskTitle(task, index)}**${status}`);
      for (const [key, value] of Object.entries(task)) {
        if (['id', 'title', 'description', 'status'].includes(key) || value === undefined) continue;
        const text = scalarText(value).trim();
        if (!text) continue;
        if (text.includes('\n')) {
          lines.push(`   - **${planLabel(key)}**:`);
          for (const line of text.split('\n')) {
            lines.push(`     ${line}`);
          }
        } else {
          lines.push(`   - **${planLabel(key)}**: ${text}`);
        }
      }
    }
    lines.push('');
  } else if (plan?.pendingTitle) {
    lines.push(`_Planning: ${scalarText(plan.pendingTitle)}_`, '');
  }

  for (const [key, value] of Object.entries(sanitized)) {
    if (['tasks', 'goal', 'title'].includes(key)) continue;
    appendMarkdownValue(lines, key, value, 4);
  }

  return lines.join('\n').trim();
}

// ── Panel renderer ────────────────────────────────────────────────────

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

  // ── 헤더 (제목·뱃지·액션 버튼) ──
  const header = document.createElement('div');
  header.className = 'plan-header';
  const titleGroup = document.createElement('div');
  titleGroup.className = 'plan-title';
  const title = document.createElement('strong');
  title.textContent = 'Plan';
  const count = document.createElement('span');
  count.className = 'plan-title-count';
  count.textContent = `${tasks.length} task${tasks.length === 1 ? '' : 's'}`;
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
  jsonToggle.title = '원본 JSON 보기';
  const openMarkdown = document.createElement('button');
  openMarkdown.type = 'button';
  openMarkdown.textContent = 'Open MD';
  openMarkdown.title = '에디터에서 전체 마크다운으로 열기';
  openMarkdown.addEventListener('click', () => onOpenMarkdown(plan));
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.textContent = 'Cancel';
  cancel.title = '이 plan을 취소하고 runner plan 상태를 초기화';
  cancel.addEventListener('click', () => onCancel?.());
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.textContent = 'Delete';
  remove.title = '현재 세션에서 plan 제거';
  remove.className = 'danger';
  remove.addEventListener('click', () => onDelete?.());
  if (canReview && !isComplete) actions.append(approve, reject);
  if (isActivePlan) actions.append(cancel);
  actions.append(remove);
  actions.append(openMarkdown, jsonToggle);
  header.append(titleGroup, actions);

  // ── Stepper ──
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
  steps.forEach(([, label], index) => {
    const step = document.createElement('span');
    step.className = `plan-step ${index < currentIndex ? 'done' : index === currentIndex ? 'active' : ''}`;
    step.textContent = label;
    stepper.appendChild(step);
  });

  // ── 짧은 상태 텍스트 (한 줄 요약만) ──
  const summary = document.createElement('div');
  summary.className = 'plan-summary-line';
  if (plan?.goal || plan?.title) {
    summary.textContent = scalarText(plan.goal || plan.title);
  } else if (plan?.pendingTitle) {
    summary.textContent = `Planning: ${plan.pendingTitle}`;
    summary.classList.add('plan-summary-pending');
  } else if (tasks.length) {
    summary.textContent = `${tasks.length} task${tasks.length === 1 ? '' : 's'}`;
  } else {
    summary.textContent = 'Planning is in progress.';
    summary.classList.add('plan-summary-pending');
  }

  // ── JSON 토글 (기본 숨김) ──
  const jsonTree = document.createElement('pre');
  jsonTree.className = 'plan-json-tree';
  jsonTree.textContent = JSON.stringify(plan, null, 2);
  jsonTree.hidden = true;
  jsonToggle.addEventListener('click', () => {
    jsonTree.hidden = !jsonTree.hidden;
    jsonToggle.classList.toggle('active', !jsonTree.hidden);
  });

  // ── 조립 ──
  panelEl.append(header, stepper, summary, jsonTree);
  panelEl.hidden = false;
}
