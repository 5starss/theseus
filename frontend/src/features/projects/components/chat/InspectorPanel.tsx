import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Layout, FileCode, CheckCircle, RotateCcw } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';
import { useToolGenerationSSE } from '../../hooks/useToolGenerationSSE';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolPlanMode } from '../../types/chat';

export function InspectorPanel() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();

  const {
    currentPlan, toolResult, activeTab, isBuilding, progressInfo,
    draftPhase, commentMode, draftComments, currentToolPlanId, planVersion,
    currentToolId, isGenerating, isClosed,
  } = useChatSessionStore(useShallow(state => ({
    currentPlan: state.currentPlan,
    toolResult: state.toolResult,
    activeTab: state.activeTab,
    isBuilding: state.isBuilding,
    progressInfo: state.progressInfo,
    draftPhase: state.draftPhase,
    commentMode: state.commentMode,
    draftComments: state.draftComments,
    currentToolPlanId: state.currentToolPlanId,
    planVersion: state.planVersion,
    currentToolId: state.currentToolId,
    isGenerating: state.isGenerating,
    isClosed: state.isClosed,
  })));

  const {
    setActiveTab, setIsBuilding, setCommentMode, setDraftComment,
    clearDraftComments, setIsGenerating, addMessage,
  } = useChatSessionStore(useShallow(state => ({
    setActiveTab: state.setActiveTab,
    setIsBuilding: state.setIsBuilding,
    setCommentMode: state.setCommentMode,
    setDraftComment: state.setDraftComment,
    clearDraftComments: state.clearDraftComments,
    setIsGenerating: state.setIsGenerating,
    addMessage: state.addMessage,
  })));

  const { connectSSE } = useToolGenerationSSE();
  const [isApproving, setIsApproving] = useState(false);

  // 수정 요청 버튼 클릭 핸들러 (설계 단계)
  const handleRequestFeedbackClick = async () => {
    if (commentMode) {
      if (!projectId || !sessionId || !currentToolPlanId) return;

      // draftComments를 feedbackItems 형식으로 변환
      const feedbackItems = Object.entries(draftComments)
        .filter(([, comment]) => comment.trim())
        .map(([blockId, comment]) => ({ blockId, comment }));

      if (feedbackItems.length === 0) {
        toast.warning('수정 요청 사항을 하나 이상 입력해주세요.');
        return;
      }

      // 사용자 피드백 메시지 추가
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'USER',
        content: `설계안에 대한 수정 요청 사항을 전송했습니다.\n${feedbackItems.map(item => `- [${item.blockId}] ${item.comment}`).join('\n')}`,
        createdAt: new Date().toISOString()
      });

      // 어시스턴트 로딩 메시지 추가
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'ASSISTANT',
        content: '',
        createdAt: new Date().toISOString()
      });

      setIsGenerating(true);
      setCommentMode(false);

      try {
        const result = await chatApi.regenerateToolPlan(
          projectId,
          sessionId,
          currentToolPlanId,
          {
            basePlanVersion: planVersion,
            feedbackItems,
            mode: ToolPlanMode.PLAN
          }
        );

        // SSE 구독 시작
        connectSSE(result.sseUrl, 'PLAN', result.runId);
        clearDraftComments();
      } catch (err) {
        console.error('Regeneration plan request failed:', err);
        setIsGenerating(false);
        toast.error('수정 요청에 실패했습니다.');
      }
    } else {
      // 수정 요청 모드 진입
      setCommentMode(true);
      setActiveTab('plan');
    }
  };

  // 설계 확정 및 툴 빌드 핸들러
  const handleBuildTool = async () => {
    if (!projectId || !sessionId || !currentToolPlanId) return;

    setIsBuilding(true);
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'SYSTEM',
      content: '설계안이 확정되었습니다. 이제 도구 생성을 시작합니다.',
      createdAt: new Date().toISOString()
    });

    try {
      const fileName = `tool_${Date.now()}`;
      const result = await chatApi.buildTool(
        projectId,
        sessionId,
        currentToolPlanId,
        {
          basePlanVersion: planVersion,
          fileName
        }
      );

      // SSE 구독 시작
      connectSSE(result.sseUrl, 'BUILD', result.toolId);
    } catch (err) {
      console.error('Build tool request failed:', err);
      setIsBuilding(false);
      toast.error('도구 생성 요청에 실패했습니다.');
    }
  };

  // 최종 승인 요청 핸들러
  const handleApprove = async () => {
    if (!projectId || !currentToolId) return;
    setIsApproving(true);
    try {
      await chatApi.requestToolApproval(projectId, currentToolId);
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'SYSTEM_NOTICE',
        content: '도구 생성이 최종 승인되었습니다.',
        createdAt: new Date().toISOString()
      });
      toast.success('최종 승인 요청이 완료되었습니다.');
    } catch (e) {
      console.error('Approval failed:', e);
      toast.error('승인 요청에 실패했습니다.');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full p-6">
      {/* Tabs Header */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'plan' | 'result')} className="w-full h-full flex flex-col">
        <div className="flex items-center justify-between mb-6 shrink-0">
          <TabsList className="bg-transparent border-b border-slate-700/50 p-0 rounded-none w-full justify-start gap-6">
            <TabsTrigger
              value="plan"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:text-blue-400 data-[state=active]:border-b-2 data-[state=active]:border-blue-400 rounded-none px-1 pb-2 text-slate-400 flex items-center gap-2 transition-all shadow-none border-b-2 border-transparent font-medium"
            >
              <Layout className="w-3.5 h-3.5" />
              플랜
            </TabsTrigger>
            <TabsTrigger
              value="result"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:text-blue-400 data-[state=active]:border-b-2 data-[state=active]:border-blue-400 rounded-none px-1 pb-2 text-slate-400 flex items-center gap-2 transition-all shadow-none border-b-2 border-transparent font-medium"
              disabled={!toolResult && !isBuilding}
            >
              <FileCode className="w-3.5 h-3.5" />
              도구
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Progress (Always visible if generating/building) */}
        {(isGenerating || isBuilding) && (
          <div className="bg-[#0d1c2d] border border-blue-500/30 rounded-lg p-4 mb-6 shrink-0 animate-pulse">
            <div className="flex justify-between items-end mb-3">
              <div>
                <div className="text-[10px] text-blue-400/70 tracking-wider mb-1 uppercase">
                  {isBuilding ? 'Building Tool' : 'Generating Plan'}
                </div>
                <div className="text-sm text-blue-100 font-medium">
                  {isBuilding ? '소스 코드 생성 및 빌드 중...' : (progressInfo?.step || '분석 중...')}
                </div>
              </div>
              <div className="text-xl text-blue-400 font-medium font-mono">
                {isBuilding ? '...' : (progressInfo ? `${progressInfo.percent}%` : '0%')}
              </div>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)] transition-all duration-300"
                style={{ width: isBuilding ? '100%' : `${progressInfo?.percent || 0}%` }}
              />
            </div>
          </div>
        )}

        {/* Tab Content Area */}
        <div className="flex-1 overflow-hidden min-h-0 relative">
          <TabsContent value="plan" className="h-full m-0 overflow-y-auto pr-2 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {currentPlan ? (
              currentPlan.blocks.map(block => (
                <div key={block.blockId} className="bg-slate-800/30 border border-slate-700/50 p-4 rounded text-sm text-slate-300 flex flex-col gap-3 group hover:border-slate-600 transition-colors">
                  <div>
                    <div className="font-semibold text-blue-200 mb-1 flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
                      {block.title}
                    </div>
                    <div className="text-slate-400 leading-relaxed whitespace-pre-wrap">{block.content}</div>
                  </div>

                  {commentMode && (
                    <div className="mt-2 animate-in slide-in-from-top-2 duration-200">
                      <textarea
                        className="w-full bg-[#051424] border border-slate-700 rounded p-2 text-slate-300 text-sm focus:outline-none focus:border-blue-400/50 resize-none min-h-[60px]"
                        placeholder="이 항목에 대한 수정 요청사항을 입력하세요..."
                        value={draftComments[block.blockId] || ''}
                        onChange={(e) => setDraftComment(block.blockId, e.target.value)}
                      />
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm gap-4">
                <Layout className="w-12 h-12 opacity-10" />
                AI가 설계를 생성하면 여기에 표시됩니다.
              </div>
            )}
          </TabsContent>

          <TabsContent value="result" className="h-full m-0 overflow-hidden">
            {toolResult ? (
              <div className="h-full flex flex-col bg-[#051424] border border-slate-700/50 rounded overflow-hidden">
                <div className="bg-slate-800/50 px-4 py-2 border-b border-slate-700/50 flex justify-between items-center shrink-0">
                  <div className="text-[10px] text-slate-500 font-mono tracking-wider">GENERATED SOURCE</div>
                  <div className="text-[10px] text-green-400 flex items-center gap-1 font-medium">
                    <CheckCircle className="w-3 h-3" />
                    READY TO APPROVE
                  </div>
                </div>
                <div className="flex-1 overflow-auto font-mono text-xs leading-relaxed scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                  <SyntaxHighlighter
                    language="json"
                    style={vscDarkPlus}
                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent', height: '100%' }}
                  >
                    {JSON.stringify(toolResult, null, 2)}
                  </SyntaxHighlighter>
                </div>
              </div>
            ) : isBuilding ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm gap-4">
                <FileCode className="w-12 h-12 opacity-10 animate-pulse" />
                도구를 빌드하고 있습니다...
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm gap-4">
                <FileCode className="w-12 h-12 opacity-10" />
                설계안을 확정한 후 빌드를 시작하세요.
              </div>
            )}
          </TabsContent>
        </div>

        {/* Footer Actions */}
        <div className="pt-6 shrink-0 flex gap-3">
          {activeTab === 'plan' ? (
            <>
              <button
                disabled={draftPhase !== 'REVIEW' || isGenerating || isBuilding || isClosed}
                onClick={handleRequestFeedbackClick}
                className={`flex-1 border py-3 rounded text-sm transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2
                  ${commentMode
                    ? 'bg-blue-500 text-white border-blue-500 hover:bg-blue-600'
                    : 'border-slate-500 text-blue-100 hover:bg-slate-800'
                  }`}
              >
                {commentMode ? '수정 요청 보내기' : '플랜 재생성'}
                {!commentMode && <RotateCcw className="w-4 h-4" />}
              </button>
              <button
                onClick={handleBuildTool}
                disabled={draftPhase !== 'REVIEW' || commentMode || isBuilding || isGenerating || isClosed}
                className="flex-1 bg-blue-400 hover:bg-blue-500 text-[#00315d] font-bold py-3 rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isBuilding ? '빌드 중...' : '도구 생성'}
                {!isBuilding && <CheckCircle className="w-4 h-4" />}
              </button>
            </>
          ) : (
            <>
              <button
                disabled={isApproving || isGenerating || isClosed}
                onClick={() => {
                  setCommentMode(true);
                  setActiveTab('plan');
                }}
                className="flex-1 border border-slate-500 text-blue-100 py-3 rounded text-sm transition-colors font-medium hover:bg-slate-800 flex items-center justify-center gap-2"
              >
                다시 생성 요청
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                onClick={handleApprove}
                disabled={!toolResult || isApproving || isClosed}
                className="flex-1 bg-blue-400 hover:bg-blue-500 text-[#00315d] font-bold py-3 rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isApproving ? '승인 요청 중...' : '최종 생성 승인'}
                {!isApproving && <CheckCircle className="w-4 h-4" />}
              </button>
            </>
          )}
        </div>
      </Tabs>
    </div>
  );
}
