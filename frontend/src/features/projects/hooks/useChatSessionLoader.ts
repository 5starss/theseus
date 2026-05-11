import { useEffect, useState, useCallback } from 'react';
import { chatApi } from '../api/chat';
import { toolApi } from '@/features/tools/api';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import { useToolGenerationSSE } from './useToolGenerationSSE';
import type { StructuredPlan, DraftPhase } from '../types/chat';

/**
 * 채팅 세션의 초기 데이터 로딩 및 진행 중인 생성 작업 복구를 담당하는 훅.
 *
 * 책임:
 *   1. 세션 상세 데이터 로딩 (메시지, Plan, Phase 등)
 *   2. Tool 상세 정보로 Plan 보강 (structuredPlanJson 파싱)
 *   3. 진행 중인 생성/빌드 작업 감지 및 SSE 재연결
 */
export function useChatSessionLoader(projectId?: string, sessionId?: string) {
  const [isLoading, setIsLoading] = useState(true);
  const initSession = useChatSessionStore(state => state.initSession);
  const setIsGenerating = useChatSessionStore(state => state.setIsGenerating);
  const setIsBuilding = useChatSessionStore(state => state.setIsBuilding);
  const setProgressInfo = useChatSessionStore(state => state.setProgressInfo);
  const updateLastMessageContent = useChatSessionStore(state => state.updateLastMessageContent);
  const { connectSSE } = useToolGenerationSSE();

  /**
   * Tool 상세 정보를 조회하여 Plan/Phase/Version 정보를 보강합니다.
   */
  const enrichWithToolDetail = useCallback(async (
    projId: string,
    toolId: string | null,
    phase: DraftPhase,
    draftVersion: number,
    planVersion: number,
    plan: StructuredPlan | null,
    mounted: boolean,
  ) => {
    let loadedPlan = plan;
    let loadedPhase = phase;
    let loadedDraftVersion = draftVersion;
    let loadedPlanVersion = planVersion;

    if (toolId) {
      try {
        const toolDetail = await toolApi.getTool(projId, toolId);
        if (toolDetail && mounted) {
          if (toolDetail.structuredPlanJson) {
            try {
              loadedPlan = JSON.parse(toolDetail.structuredPlanJson);
            } catch (e) {
              console.error('Failed to parse structuredPlanJson:', e);
            }
          }
          loadedPhase = toolDetail.draftPhase;
          loadedDraftVersion = toolDetail.draftVersion;
          loadedPlanVersion = toolDetail.draftVersion;
        }
      } catch (err) {
        console.warn('Failed to load tool detail for recovery:', err);
      }
    }

    return { plan: loadedPlan, phase: loadedPhase, draftVersion: loadedDraftVersion, planVersion: loadedPlanVersion };
  }, []);

  /**
   * 빌드/설계 중이던 작업을 감지하여 SSE를 재연결합니다.
   */
  const recoverActiveGeneration = useCallback(async (
    projId: string,
    sessId: string,
    toolId: string | null,
    toolPlanId: string | null,
    mounted: boolean,
  ) => {
    if (!toolId && !toolPlanId) return;

    try {
      // 1. 빌드 상태 조회
      if (toolId) {
        const stateResult = await chatApi.getToolGenerationState(projId, sessId, toolId);
        if ((stateResult.status === 'GENERATING' || stateResult.status === 'IN_PROGRESS') && mounted) {
          setIsGenerating(true);
          setIsBuilding(true);
          setProgressInfo({
            step: stateResult.message || '빌드 중...',
            message: stateResult.message || '',
            percent: stateResult.progressRate ?? 0,
          });
          if (stateResult.content) {
            updateLastMessageContent(stateResult.content);
          }
          const sseUrl = `/api/v1/projects/${projId}/sessions/${sessId}/tools/${toolId}/generation-state/stream`;
          connectSSE(sseUrl, 'BUILD', Number(toolId));
          return; // 빌드 중이면 Plan 상태 복구는 스킵
        }
      }

      // 2. 설계 상태 조회
      if (toolPlanId) {
        const planStateResult = await chatApi.getToolPlanGenerationState(projId, sessId, toolPlanId);
        if ((planStateResult.status === 'GENERATING' || planStateResult.status === 'IN_PROGRESS') && mounted) {
          setIsGenerating(true);
          setProgressInfo({
            step: planStateResult.message || '설계안 생성 중...',
            message: planStateResult.message || '',
            percent: planStateResult.progressRate ?? 0,
          });
          if (planStateResult.content) {
            updateLastMessageContent(planStateResult.content);
          }
          if (planStateResult.runId) {
            const sseUrl = `/api/v1/projects/${projId}/sessions/${sessId}/tool-plan-runs/${planStateResult.runId}/events`;
            connectSSE(sseUrl, 'PLAN', planStateResult.runId);
          }
        }
      }
    } catch (stateError) {
      console.warn('진행 중인 생성 작업 확인 실패 (정상적인 종료 상태일 수 있음):', stateError);
    }
  }, [setIsGenerating, setIsBuilding, setProgressInfo, updateLastMessageContent, connectSSE]);

  useEffect(() => {
    let isMounted = true;

    const loadSessionData = async () => {
      if (!projectId || !sessionId) return;
      setIsLoading(true);

      try {
        const details = await chatApi.getSessionDetails(projectId, sessionId);
        if (!isMounted) return;

        const messages = details.messages || [];
        let currentToolIdVal = details.currentToolId;
        let currentToolPlanIdVal = details.currentToolPlanId;

        // 복구 로직: DTO에 값이 없는 경우 히스토리에서 추출
        if (!currentToolIdVal && !currentToolPlanIdVal && messages.length > 0) {
          const lastToolMessage = [...messages].reverse().find(m => m.toolId);
          if (lastToolMessage) {
            currentToolIdVal = String(lastToolMessage.toolId);
            currentToolPlanIdVal = String(lastToolMessage.toolId);
          }
        }

        // Tool 상세로 Plan 정보 보강
        const enriched = await enrichWithToolDetail(
          projectId,
          currentToolIdVal,
          details.draftPhase,
          details.draftVersion,
          details.planVersion,
          details.currentPlan,
          isMounted
        );

        initSession({
          messages,
          plan: enriched.plan,
          phase: enriched.phase,
          toolId: currentToolIdVal,
          toolPlanId: currentToolPlanIdVal,
          toolResult: details.draftSnapshot,
          title: details.title || '새 세션',
          isClosed: details.isClosed,
          planVersion: enriched.planVersion,
          draftVersion: enriched.draftVersion,
        });

        // 진행 중인 생성 작업 복구
        await recoverActiveGeneration(
          projectId,
          sessionId,
          currentToolIdVal,
          currentToolPlanIdVal,
          isMounted,
        );
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
  }, [projectId, sessionId, initSession, enrichWithToolDetail, recoverActiveGeneration]);

  return { isLoading };
}
