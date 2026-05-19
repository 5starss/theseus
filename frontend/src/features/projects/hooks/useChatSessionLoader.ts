import { useCallback, useEffect, useState } from 'react';
import { chatApi } from '../api/chat';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { useToolGenerationSSE } from './useToolGenerationSSE';
import { parseStructuredPlanJson } from '../utils/structuredPlan';
import type { CurrentPlanRecovery, DraftPhase } from '../types/chat';

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
      return 'FAILED';
    default:
      return null;
  }
}

function planStatusFrom(status?: string | null) {
  return status === 'SKIPPED' ? null : status || null;
}

function isRunningPlan(currentPlan: CurrentPlanRecovery | null): currentPlan is CurrentPlanRecovery & { runId: string } {
  return Boolean(
    currentPlan?.runId
    && (currentPlan.status === 'REQUESTED' || currentPlan.status === 'GENERATING' || currentPlan.status === 'BUILDING')
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

    try {
      const detail = await chatApi.getToolPlanDetail(projId, sessId, String(toolPlanId));
      return parseStructuredPlanJson(detail.structuredPlanJson, 'ChatLoader');
    } catch (error) {
      console.warn('Failed to load ToolPlan detail:', error);
      return null;
    }
  }, []);

  const recoverRunningPlan = useCallback(async (
    projId: string,
    sessId: string,
    currentPlan: CurrentPlanRecovery | null,
    mounted: boolean,
  ) => {
    if (!isRunningPlan(currentPlan)) return;

    setIsGenerating(true);

    try {
      const state = await chatApi.getToolPlanRunState(projId, sessId, currentPlan.runId);
      if (!mounted) return;

      setProgressInfo({
        step: state.message || 'PLAN generation in progress',
        message: state.message || '',
        percent: state.progressRate ?? 0,
      });
      if (state.content) {
        updateLastMessageContent(state.content);
      }
    } catch (error) {
      console.warn('Failed to recover ToolPlan run state:', error);
    }

    if (!mounted) return;

    const flow = currentPlan.status === 'BUILDING' ? 'BUILD' : 'PLAN';
    const ssePath = `/api/v1/projects/${projId}/sessions/${sessId}/tool-plan-runs/${currentPlan.runId}/events`;

    console.log(`[ChatLoader] Recovering ${flow} SSE connection:`, ssePath);
    connectSSE(ssePath, flow, currentPlan.runId);
  }, [connectSSE, setIsGenerating, setProgressInfo, updateLastMessageContent]);

  useEffect(() => {
    let isMounted = true;

    const loadSessionData = async () => {
      if (!projectId || !sessionId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);

      try {
        const details = await chatApi.getSessionDetails(projectId, sessionId);
        if (!isMounted) return;

        const currentPlan = details.currentPlan;
        const structuredPlan = await loadStructuredPlan(projectId, sessionId, currentPlan?.toolPlanId);
        if (!isMounted) return;

        const phase = details.createdTool
          ? phaseFromStatus(details.createdTool.status) || 'BUILT'
          : phaseFromStatus(currentPlan?.status);

        initSession({
          messages: details.messages || [],
          plan: structuredPlan,
          phase,
          toolId: details.createdTool?.toolId ? String(details.createdTool.toolId) : null,
          toolPlanGroupId: currentPlan?.toolPlanGroupId ? String(currentPlan.toolPlanGroupId) : null,
          toolPlanId: currentPlan?.toolPlanId ? String(currentPlan.toolPlanId) : null,
          runId: currentPlan?.runId || null,
          planStatus: planStatusFrom(currentPlan?.status),
          createdTool: details.createdTool,
          toolResult: details.createdTool ? { ...details.createdTool } : null,
          title: details.title || 'Chat session',
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
