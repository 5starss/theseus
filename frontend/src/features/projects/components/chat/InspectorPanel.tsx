import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CheckCircle, FileCode, Layout, MessageSquarePlus, RotateCcw, X } from 'lucide-react';
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
    currentPlan, toolResult, activeTab, isBuilding,
    draftPhase, commentMode, draftComments, currentToolPlanId, planVersion,
    isGenerating, isClosed, createdTool, selectedRemoteWorkspaceId,
  } = useChatSessionStore(useShallow(state => ({
    currentPlan: state.currentPlan,
    toolResult: state.toolResult,
    activeTab: state.activeTab,
    isBuilding: state.isBuilding,
    draftPhase: state.draftPhase,
    commentMode: state.commentMode,
    draftComments: state.draftComments,
    currentToolPlanId: state.currentToolPlanId,
    planVersion: state.planVersion,
    isGenerating: state.isGenerating,
    isClosed: state.isClosed,
    createdTool: state.createdTool,
    selectedRemoteWorkspaceId: state.selectedRemoteWorkspaceId,
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
  const [activeFeedbackTarget, setActiveFeedbackTarget] = useState<string | null>(null);
  const isReviewable = draftPhase === 'REVIEW' && Boolean(currentToolPlanId);

  const openFeedbackTarget = (target: string) => {
    if (!isReviewable || isGenerating || isBuilding || isClosed) return;
    setCommentMode(true);
    setActiveTab('plan');
    setActiveFeedbackTarget(target);
  };

  const renderFeedbackButton = (target: string, label = 'Feedback') => {
    if (!isReviewable || isGenerating || isBuilding || isClosed) return null;
    return (
      <button
        type="button"
        title={label}
        aria-label={label}
        onClick={() => openFeedbackTarget(target)}
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-700 bg-slate-900/30 text-slate-400 transition-colors hover:border-blue-400/60 hover:bg-blue-400/10 hover:text-blue-200 focus:border-blue-400/60 focus:outline-none"
      >
        <MessageSquarePlus className="h-3.5 w-3.5" />
        <span className="sr-only">{label}</span>
      </button>
    );
  };

  const renderFeedbackInput = (target: string, placeholder = '이 항목에 대한 수정 요청을 입력하세요.') => {
    if (!commentMode) return null;
    if (activeFeedbackTarget !== target && draftComments[target] === undefined) return null;

    return (
      <textarea
        className="mt-3 min-h-[72px] w-full resize-none rounded-md border border-blue-400/30 bg-[#071827] p-3 text-sm leading-6 text-slate-200 placeholder:text-slate-500 focus:border-blue-400/70 focus:outline-none"
        placeholder={placeholder}
        value={draftComments[target] || ''}
        onChange={(e) => setDraftComment(target, e.target.value)}
        autoFocus={activeFeedbackTarget === target}
      />
    );
  };

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
      content: `PLAN 수정 요청:\n${feedbackItems.map(item => `- ${item.blockId}: ${item.comment}`).join('\n')}`,
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
          mode: ToolPlanMode.PLAN,
          remoteWorkspaceId: selectedRemoteWorkspaceId ?? undefined
        }
      );

      connectSSE(result.sseUrl, 'PLAN', result.runId);
      clearDraftComments();
      setActiveFeedbackTarget(null);
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

        <div className="flex-1 overflow-hidden min-h-0 relative">
          <TabsContent value="plan" className="h-full m-0 overflow-y-auto pr-2 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {currentPlan ? (
              <>
                {currentPlan.sections && currentPlan.sections.length > 0 && (
                  <div className="rounded-md border border-slate-700/50 bg-[#071424]/70 px-4 py-3 text-sm text-slate-300">
                    {currentPlan.sections.map((section, index) => (
                      <section
                        key={section.sectionId}
                        className={`${index > 0 ? 'mt-3 border-t border-slate-800/80 pt-3' : ''}`}
                      >
                        <div className={`mb-1 text-xs font-semibold leading-5 ${
                          section.tone === 'warning' ? 'text-amber-200' : 'text-blue-100'
                        }`}>
                          {section.title}
                        </div>
                        <div className="whitespace-pre-wrap text-[12px] leading-5 text-slate-400 [overflow-wrap:anywhere]">
                          {section.content}
                        </div>
                      </section>
                    ))}
                  </div>
                )}

                {currentPlan.blocks.map(block => (
                  <div
                    key={block.blockId}
                    className={`group rounded-md border border-slate-700/60 bg-[#0a1624]/70 p-4 text-sm text-slate-300 shadow-sm transition-colors hover:border-slate-600/80 ${
                      block.parentId ? 'ml-3 border-l-2 border-l-blue-400/30' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 pb-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start gap-2">
                          <div className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                          <div className="min-w-0">
                            <h3 className="text-sm font-semibold leading-5 text-blue-100 [overflow-wrap:anywhere]">
                              {block.title}
                            </h3>
                            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] leading-4 text-slate-500">
                              <span className="font-mono text-slate-400">{block.blockId}</span>
                              {block.tier && <span>{block.tier}</span>}
                              {block.status && <span>{block.status}</span>}
                              {block.parentId && <span>Parent {block.parentId}</span>}
                            </div>
                          </div>
                        </div>
                      </div>
                      {renderFeedbackButton(block.blockId, 'Task feedback')}
                    </div>

                    {renderFeedbackInput(block.blockId, '이 task 전체에 대한 수정 요청을 입력하세요.')}

                    {block.fields && block.fields.length > 0 ? (
                      <div className="border-t border-slate-700/50">
                        {block.fields.map((field, index) => (
                          <section
                            key={field.feedbackTarget}
                            className={`py-3 ${index > 0 ? 'border-t border-slate-800/80' : ''}`}
                          >
                            <div className="flex items-start gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="mb-1 text-xs font-semibold leading-5 text-slate-300">
                                  {field.label}
                                </div>
                                <div className="whitespace-pre-wrap text-[13px] leading-6 text-slate-400 [overflow-wrap:anywhere]">
                                  {field.value}
                                </div>
                              </div>
                              {renderFeedbackButton(field.feedbackTarget, `${field.label} feedback`)}
                            </div>
                            {renderFeedbackInput(field.feedbackTarget, `${field.label} 항목에 대한 수정 요청을 입력하세요.`)}
                          </section>
                        ))}
                      </div>
                    ) : (
                      <div className="border-t border-slate-700/50 pt-3 text-[13px] leading-6 text-slate-400 whitespace-pre-wrap [overflow-wrap:anywhere]">
                        {block.content}
                      </div>
                    )}
                  </div>
                ))}
              </>
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
              {commentMode ? (
                <button
                  onClick={() => {
                    setCommentMode(false);
                    setActiveFeedbackTarget(null);
                    clearDraftComments();
                  }}
                  className="flex-1 border border-slate-500 text-slate-300 hover:bg-slate-800 py-3 rounded text-sm transition-colors font-medium flex items-center justify-center gap-2"
                >
                  취소
                  <X className="w-4 h-4" />
                </button>
              ) : (
                <button
                  disabled={!isReviewable || isGenerating || isBuilding || isClosed}
                  onClick={handleRequestFeedbackClick}
                  className="flex-1 border border-slate-500 text-blue-100 hover:bg-slate-800 py-3 rounded text-sm transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  수정 요청
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}

              {commentMode ? (
                <button
                  disabled={!isReviewable || isGenerating || isBuilding || isClosed}
                  onClick={handleRequestFeedbackClick}
                  className="flex-1 bg-blue-500 text-white border-blue-500 hover:bg-blue-600 py-3 rounded text-sm transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  수정 요청 보내기
                </button>
              ) : (
                <button
                  onClick={handleApprovalRequest}
                  disabled={!isReviewable || isApproving || isGenerating || isClosed}
                  className="flex-1 bg-blue-400 hover:bg-blue-500 text-[#00315d] font-bold py-3 rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isApproving ? '요청 중' : '생성 승인 요청'}
                  {!isApproving && <CheckCircle className="w-4 h-4" />}
                </button>
              )}
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
