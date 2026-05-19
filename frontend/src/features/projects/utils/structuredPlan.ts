import type { PlanBlock, PlanField, StructuredPlan } from '../types/chat';

type StructuredPlanRecord = Record<string, unknown>;

const TASK_FIELD_SPECS: Array<{ fieldId: string; label: string; keys: string[] }> = [
  { fieldId: 'problem', label: 'Problem', keys: ['problem'] },
  { fieldId: 'solution', label: 'Solution', keys: ['solution'] },
  { fieldId: 'expected_effect', label: 'Expected effect', keys: ['expected_effect', 'expectedEffect'] },
  { fieldId: 'description', label: 'Description', keys: ['description'] },
  { fieldId: 'target_files', label: 'Target files', keys: ['target_files', 'targetFiles'] },
  { fieldId: 'integration_points', label: 'Integration points', keys: ['integration_points', 'integrationPoints'] },
  { fieldId: 'sequential_dependencies', label: 'Sequential dependencies', keys: ['sequential_dependencies', 'sequentialDependencies'] },
  { fieldId: 'plan_b', label: 'Plan B', keys: ['plan_b', 'planB'] },
  { fieldId: 'safe_alternative', label: 'Safe alternative', keys: ['safe_alternative', 'safeAlternative'] },
  { fieldId: 'risks', label: 'Risks', keys: ['risks'] },
];

function isRecord(value: unknown): value is StructuredPlanRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function textFrom(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return null;
}

function formattedValueFrom(value: unknown): string | null {
  const text = textFrom(value);
  if (text) return text;

  if (Array.isArray(value)) {
    const items = value
      .map(item => formattedValueFrom(item))
      .filter((item): item is string => Boolean(item));
    return items.length ? items.map(item => `- ${item}`).join('\n') : null;
  }

  if (isRecord(value)) {
    return JSON.stringify(value, null, 2);
  }

  return null;
}

function firstValueFrom(record: StructuredPlanRecord, keys: string[]): unknown {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) return record[key];
  }
  return undefined;
}

function versionFrom(parsed: StructuredPlanRecord): string | number {
  const version = parsed.version;
  if (typeof version === 'string' || typeof version === 'number') return version;

  const planVersion = parsed.planVersion;
  if (typeof planVersion === 'string' || typeof planVersion === 'number') return planVersion;

  return 1;
}

function blockFrom(value: unknown, index: number): PlanBlock {
  if (!isRecord(value)) {
    return {
      blockId: `block-${index + 1}`,
      title: `Block ${index + 1}`,
      content: formattedValueFrom(value) || '',
    };
  }

  return {
    blockId: textFrom(value.blockId) || textFrom(value.id) || `block-${index + 1}`,
    title: textFrom(value.title) || textFrom(value.name) || `Block ${index + 1}`,
    content: formattedValueFrom(value.content) || '',
  };
}

function taskContentFrom(task: StructuredPlanRecord): string {
  const parts = TASK_FIELD_SPECS
    .map(({ keys, label }) => {
      const value = formattedValueFrom(firstValueFrom(task, keys));
      return value ? `${label}\n${value}` : null;
    })
    .filter((part): part is string => Boolean(part));

  if (parts.length > 0) {
    return parts.join('\n\n');
  }

  return formattedValueFrom(task.content) || JSON.stringify(task, null, 2);
}

function taskFieldsFrom(task: StructuredPlanRecord, blockId: string): PlanField[] {
  return TASK_FIELD_SPECS
    .map(({ fieldId, label, keys }) => {
      const value = formattedValueFrom(firstValueFrom(task, keys));
      if (!value) return null;
      return {
        fieldId,
        label,
        value,
        feedbackTarget: `${blockId}.${fieldId}`,
      };
    })
    .filter((field): field is PlanField => Boolean(field));
}

function taskBlockFrom(value: unknown, index: number): PlanBlock {
  if (!isRecord(value)) {
    return {
      blockId: `task-${index + 1}`,
      title: `Task ${index + 1}`,
      content: formattedValueFrom(value) || '',
    };
  }

  const blockId = textFrom(value.blockId) || textFrom(value.id) || `task-${index + 1}`;
  return {
    blockId,
    title: textFrom(value.title) || textFrom(value.name) || textFrom(value.id) || `Task ${index + 1}`,
    content: taskContentFrom(value),
    fields: taskFieldsFrom(value, blockId),
    parentId: textFrom(value.parent_id) || textFrom(value.parentId),
    tier: textFrom(value.tier),
    status: textFrom(value.status),
  };
}

export function parseStructuredPlanJson(
  structuredPlanJson?: string | null,
  logPrefix = 'ToolPlan'
): StructuredPlan | null {
  if (!structuredPlanJson) return null;

  try {
    const parsed = JSON.parse(structuredPlanJson) as unknown;
    if (!isRecord(parsed)) return null;

    if (Array.isArray(parsed.blocks)) {
      return {
        version: versionFrom(parsed),
        blocks: parsed.blocks.map(blockFrom),
      };
    }

    if (Array.isArray(parsed.tasks)) {
      return {
        version: versionFrom(parsed),
        blocks: parsed.tasks.map(taskBlockFrom),
      };
    }

    return null;
  } catch (error) {
    console.warn(`[${logPrefix}] Failed to parse structuredPlanJson:`, error);
    return null;
  }
}
