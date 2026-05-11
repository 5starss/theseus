import { useCallback, useEffect, useState } from 'react';
import { chatApi } from '../api/chat';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { useToolGenerationSSE } from './useToolGenerationSSE';
import type { CurrentPlanRecovery, DraftPhase, StructuredPlan } from '../types/chat';

function parseStructuredPlan(structuredPlanJson?: string | null): StructuredPlan | null {
  if (!structuredPlanJson) return null;

  try {
    const parsed = JSON.parse(structuredPlanJson) as StructuredPlan;
    return Array.isArray(parsed.blocks) ? parsed : null;
  } catch (error) {
    console.warn('Failed to parse structuredPlanJson:', error);
    return null;
  }
}

function phaseFromStatus(status?: string | null): DraftPhase {
  switch (status) {
    case 'REQUESTED':
    case 'GENERATING':
      return 'PLAN';
    case 'REVIEW':
      return 'REVIEW';
    case 'PENDING':
      return 'PENDING';
    case 'APPROVED':
      return 'APPROVED';
    case 'REJECTED':
      return 'REJECTED';
    case 'BUILDING':
      return 'BUILDING';
    case 'BUILT':
      return 'BUILT';
    case 'FAILED':
    case 'SKIPPED':
      return 'FAILED';
    default:
      return null;
  }
}

function isRunningPlan(currentPlan: CurrentPlanRecovery | null): currentPlan is CurrentPlanRecovery & { runId: string } {
  return Boolean(
    currentPlan?.runId
      && (currentPlan.status === 'REQUESTED' || currentPlan.status === 'GENERATING')
  );
}

export function useChatSessionLoader(projectId?: string, sessionId?: string) {
  const [isLoading, setIsLoading] = useState(true);
  const initSession = useChatSessionStore(state => state.initSession);
  const setIsGenerating = useChatSessionStore(state => state.setIsGenerating);
  const setProgressInfo = useChatSessionStore(state => state.setProgressInfo);
  const updateLastMessageContent = useChatSessionStore(state => state.updateLastMessageContent);
  const { connectSSE } = useToolGenerationSSE();

  const loadStructuredPlan = useCallback(async (
    projId: string,
    sessId: string,
    toolPlanId?: number | null,
  ) => {
    if (!toolPlanId) return null;

    const detail = await chatApi.getToolPlanDetail(projId, sessId, String(toolPlanId));
    return parseStructuredPlan(detail.structuredPlanJson);
  }, []);

  const recoverRunningPlan = useCallback(async (
    projId: string,
    sessId: string,
    currentPlan: CurrentPlanRecovery | null,
    mounted: boolean,
  ) => {
    if (!isRunningPlan(currentPlan)) return;

    const state = await chatApi.getToolPlanRunState(projId, sessId, currentPlan.runId);
    if (!mounted) return;

    setIsGenerating(true);
    setProgressInfo({
      step: state.message || 'PLAN 생성 중',
      message: state.message || '',
      percent: state.progressRate ?? 0,
    });
    if (state.content) {
      updateLastMessageContent(state.content);
    }

    connectSSE(
      `/api/v1/projects/${projId}/sessions/${sessId}/tool-plan-runs/${currentPlan.runId}/events`,
      'PLAN',
      currentPlan.runId
    );
  }, [connectSSE, setIsGenerating, setProgressInfo, updateLastMessageContent]);

  useEffect(() => {
    let isMounted = true;

    const loadSessionData = async () => {
      if (!projectId || !sessionId) return;
      setIsLoading(true);

      try {
        const details = await chatApi.getSessionDetails(projectId, sessionId);
        if (!isMounted) return;

        const currentPlan = details.currentPlan;
        const structuredPlan = await loadStructuredPlan(projectId, sessionId, currentPlan?.toolPlanId);
        if (!isMounted) return;

        initSession({
          messages: details.messages || [],
          plan: structuredPlan,
          phase: phaseFromStatus(currentPlan?.status),
          toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
          toolPlanGroupId: currentPlan?.toolPlanGroupId ? String(currentPlan.toolPlanGroupId) : null,
          toolPlanId: currentPlan?.toolPlanId ? String(currentPlan.toolPlanId) : null,
          runId: currentPlan?.runId || null,
          planStatus: currentPlan?.status || null,
          createdTool: details.createdTool,
          toolResult: details.createdTool ? { ...details.createdTool } : null,
          title: details.title || '대화 세션',
          isClosed: details.isClosed,
          planVersion: currentPlan?.planVersion || 0,
          draftVersion: currentPlan?.planVersion || 0,
        });

        await recoverRunningPlan(projectId, sessionId, currentPlan, isMounted);
      } catch (error) {
        console.error('Failed to load chat session details:', error);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadSessionData();

    return () => {
      isMounted = false;
    };
  }, [projectId, sessionId, initSession, loadStructuredPlan, recoverRunningPlan]);

  return { isLoading };
}
