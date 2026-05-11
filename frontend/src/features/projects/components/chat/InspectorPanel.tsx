import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CheckCircle, FileCode, Layout, RotateCcw } from 'lucide-react';
import { useShallow } from 'zustand/react/shallow';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';
import { useToolGenerationSSE } from '../../hooks/useToolGenerationSSE';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { ToolPlanMode } from '../../types/chat';

export function InspectorPanel() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();

  const {
    currentPlan, toolResult, activeTab, isBuilding, progressInfo,
    draftPhase, commentMode, draftComments, currentToolPlanId, planVersion,
    isGenerating, isClosed, createdTool,
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
    isGenerating: state.isGenerating,
    isClosed: state.isClosed,
    createdTool: state.createdTool,
  })));

  const {
    setActiveTab, setCommentMode, setDraftComment,
    clearDraftComments, setIsGenerating, setDraftPhase, setPlanStatus, addMessage,
  } = useChatSessionStore(useShallow(state => ({
    setActiveTab: state.setActiveTab,
    setCommentMode: state.setCommentMode,
    setDraftComment: state.setDraftComment,
    clearDraftComments: state.clearDraftComments,
    setIsGenerating: state.setIsGenerating,
    setDraftPhase: state.setDraftPhase,
    setPlanStatus: state.setPlanStatus,
    addMessage: state.addMessage,
  })));

  const { connectSSE } = useToolGenerationSSE();
  const [isApproving, setIsApproving] = useState(false);
  const isReviewable = draftPhase === 'REVIEW' && Boolean(currentToolPlanId);

  const handleRequestFeedbackClick = async () => {
    if (!commentMode) {
      setCommentMode(true);
      setActiveTab('plan');
      return;
    }

    if (!projectId || !sessionId || !currentToolPlanId) return;

    const feedbackItems = Object.entries(draftComments)
      .filter(([, comment]) => comment.trim())
      .map(([blockId, comment]) => ({ blockId, comment }));

    if (feedbackItems.length === 0) {
      toast.warning('수정 요청 항목을 하나 이상 입력해 주세요.');
      return;
    }

    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'USER',
      messageType: 'TOOL_FEEDBACK',
      contentType: 'TEXT',
      content: `PLAN 수정 요청을 보냈습니다.\n${feedbackItems.map(item => `- [${item.blockId}] ${item.comment}`).join('\n')}`,
      createdAt: new Date().toISOString()
    });

    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'ASSISTANT',
      messageType: 'TOOL_PLAN_RESPONSE',
      contentType: 'MARKDOWN',
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

      connectSSE(result.sseUrl, 'PLAN', result.runId);
      clearDraftComments();
    } catch (err) {
      console.error('Regeneration plan request failed:', err);
      setIsGenerating(false);
      toast.error('수정 요청에 실패했습니다.');
    }
  };

  const handleApprovalRequest = async () => {
    if (!projectId || !currentToolPlanId) return;

    setIsApproving(true);
    try {
      await chatApi.requestToolPlanApproval(projectId, currentToolPlanId);
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'SYSTEM_NOTICE',
        messageType: 'TOOL_APPROVAL_REQUEST',
        contentType: 'TEXT',
        content: 'ToolPlan 생성 승인 요청을 보냈습니다.',
        createdAt: new Date().toISOString()
      });
      setDraftPhase('PENDING');
      setPlanStatus('PENDING');
      toast.success('생성 승인 요청이 완료되었습니다.');
    } catch (error) {
      console.error('ToolPlan approval request failed:', error);
      toast.error('생성 승인 요청에 실패했습니다.');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full p-6">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'plan' | 'result')} className="w-full h-full flex flex-col">
        <div className="flex items-center justify-between mb-6 shrink-0">
          <TabsList className="bg-transparent border-b border-slate-700/50 p-0 rounded-none w-full justify-start gap-6">
            <TabsTrigger
              value="plan"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:text-blue-400 data-[state=active]:border-b-2 data-[state=active]:border-blue-400 rounded-none px-1 pb-2 text-slate-400 flex items-center gap-2 transition-all shadow-none border-b-2 border-transparent font-medium"
            >
              <Layout className="w-3.5 h-3.5" />
              PLAN
            </TabsTrigger>
            <TabsTrigger
              value="result"
              className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:text-blue-400 data-[state=active]:border-b-2 data-[state=active]:border-blue-400 rounded-none px-1 pb-2 text-slate-400 flex items-center gap-2 transition-all shadow-none border-b-2 border-transparent font-medium"
              disabled={!createdTool && !toolResult && !isBuilding}
            >
              <FileCode className="w-3.5 h-3.5" />
              TOOL
            </TabsTrigger>
          </TabsList>
        </div>

        {(isGenerating || isBuilding) && (
          <div className="bg-[#0d1c2d] border border-blue-500/30 rounded-lg p-4 mb-6 shrink-0 animate-pulse">
            <div className="flex justify-between items-end mb-3">
              <div>
                <div className="text-[10px] text-blue-400/70 tracking-wider mb-1 uppercase">
                  {isBuilding ? 'Building Tool' : 'Generating Plan'}
                </div>
                <div className="text-sm text-blue-100 font-medium">
                  {progressInfo?.step || (isBuilding ? 'Tool 생성 중' : 'PLAN 생성 중')}
                </div>
              </div>
              <div className="text-xl text-blue-400 font-medium font-mono">
                {progressInfo ? `${progressInfo.percent}%` : '0%'}
              </div>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)] transition-all duration-300"
                style={{ width: `${progressInfo?.percent || 0}%` }}
              />
            </div>
          </div>
        )}

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
                        placeholder="이 블록에 대한 수정 요청을 입력하세요."
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
                AI가 PLAN을 생성하면 여기에 표시됩니다.
              </div>
            )}
          </TabsContent>

          <TabsContent value="result" className="h-full m-0 overflow-hidden">
            {createdTool || toolResult ? (
              <div className="h-full flex flex-col bg-[#051424] border border-slate-700/50 rounded overflow-hidden">
                <div className="bg-slate-800/50 px-4 py-2 border-b border-slate-700/50 flex justify-between items-center shrink-0">
                  <div className="text-[10px] text-slate-500 font-mono tracking-wider">CREATED TOOL</div>
                  <div className="text-[10px] text-green-400 flex items-center gap-1 font-medium">
                    <CheckCircle className="w-3 h-3" />
                    READY
                  </div>
                </div>
                <div className="flex-1 overflow-auto font-mono text-xs leading-relaxed scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                  <SyntaxHighlighter
                    language="json"
                    style={vscDarkPlus}
                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent', height: '100%' }}
                  >
                    {JSON.stringify(createdTool || toolResult, null, 2)}
                  </SyntaxHighlighter>
                </div>
              </div>
            ) : isBuilding ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm gap-4">
                <FileCode className="w-12 h-12 opacity-10 animate-pulse" />
                Tool을 생성하고 있습니다.
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-sm gap-4">
                <FileCode className="w-12 h-12 opacity-10" />
                승인 후 실제 Tool이 생성되면 여기에 표시됩니다.
              </div>
            )}
          </TabsContent>
        </div>

        <div className="pt-6 shrink-0 flex gap-3">
          {activeTab === 'plan' ? (
            <>
              <button
                disabled={!isReviewable || isGenerating || isBuilding || isClosed}
                onClick={handleRequestFeedbackClick}
                className={`flex-1 border py-3 rounded text-sm transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2
                  ${commentMode
                    ? 'bg-blue-500 text-white border-blue-500 hover:bg-blue-600'
                    : 'border-slate-500 text-blue-100 hover:bg-slate-800'
                  }`}
              >
                {commentMode ? '수정 요청 보내기' : '수정 요청'}
                {!commentMode && <RotateCcw className="w-4 h-4" />}
              </button>
              <button
                onClick={handleApprovalRequest}
                disabled={!isReviewable || commentMode || isApproving || isGenerating || isClosed}
                className="flex-1 bg-blue-400 hover:bg-blue-500 text-[#00315d] font-bold py-3 rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isApproving ? '요청 중' : '생성 승인 요청'}
                {!isApproving && <CheckCircle className="w-4 h-4" />}
              </button>
            </>
          ) : (
            <button
              disabled={isGenerating || isClosed}
              onClick={() => setActiveTab('plan')}
              className="flex-1 border border-slate-500 text-blue-100 py-3 rounded text-sm transition-colors font-medium hover:bg-slate-800 flex items-center justify-center gap-2"
            >
              PLAN 보기
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>
      </Tabs>
    </div>
  );
}
