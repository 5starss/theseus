import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';

export function InspectorPanel() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const currentPlan = useChatSessionStore(state => state.currentPlan);
  const progressInfo = useChatSessionStore(state => state.progressInfo);
  const draftPhase = useChatSessionStore(state => state.draftPhase);
  const commentMode = useChatSessionStore(state => state.commentMode);
  const setCommentMode = useChatSessionStore(state => state.setCommentMode);
  const draftComments = useChatSessionStore(state => state.draftComments);
  const setDraftComment = useChatSessionStore(state => state.setDraftComment);
  const clearDraftComments = useChatSessionStore(state => state.clearDraftComments);
  const currentToolId = useChatSessionStore(state => state.currentToolId);
  const isGenerating = useChatSessionStore(state => state.isGenerating);
  const isClosed = useChatSessionStore(state => state.isClosed);
  const setIsGenerating = useChatSessionStore(state => state.setIsGenerating);
  const setAbortController = useChatSessionStore(state => state.setAbortController);
  const addMessage = useChatSessionStore(state => state.addMessage);
  const updateLastMessageContent = useChatSessionStore(state => state.updateLastMessageContent);
  const setPlan = useChatSessionStore(state => state.setPlan);
  const setProgressInfo = useChatSessionStore(state => state.setProgressInfo);

  const [isApproving, setIsApproving] = useState(false);

  const handleRequestFeedbackClick = () => {
    if (commentMode) {
      if (!projectId || !sessionId) return;
      
      const payload = {
        message: "수정 요청",
        comments: draftComments
      };

      // Add User feedback message
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'USER',
        content: `수정 요청 사항을 전송했습니다.\n${Object.entries(draftComments).map(([k, v]) => `- [${k}] ${v}`).join('\n')}`,
        createdAt: new Date().toISOString()
      });

      // Add Assistant loading message
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'ASSISTANT',
        content: '',
        createdAt: new Date().toISOString()
      });

      setIsGenerating(true);
      setCommentMode(false);

      const abortCtrl = chatApi.generateToolStream(
        projectId,
        sessionId,
        currentToolId,
        payload,
        (ev: unknown) => {
          try {
            const event = ev as { data?: string };
            const data = event.data ? JSON.parse(event.data) : null;
            if (!data) return;
  
            if (data.type === 'chunk' && data.content) {
              updateLastMessageContent(data.content);
            } else if (data.type === 'plan') {
              setPlan(data.plan);
            } else if (data.type === 'progress') {
              setProgressInfo(data.progress);
            }
          } catch {
            const event = ev as { data?: string };
            if (event.data) {
               updateLastMessageContent(event.data);
            }
          }
        },
        (err) => {
          console.error('SSE Error during feedback:', err);
          setIsGenerating(false);
          setAbortController(null);
        },
        () => {
          setIsGenerating(false);
          setAbortController(null);
          clearDraftComments();
        }
      );
      setAbortController(abortCtrl);

    } else {
      // 수정 요청 모드 진입
      setCommentMode(true);
    }
  };

  const handleApprove = async () => {
    if (!projectId || !currentToolId) return;
    setIsApproving(true);
    try {
      await chatApi.requestToolApproval(projectId, currentToolId);
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'SYSTEM_NOTICE',
        content: '도구 생성이 성공적으로 승인되었습니다.',
        createdAt: new Date().toISOString()
      });
      // Optionally update phase to 'APPROVED' if managed by client, 
      // but usually the backend stream or response dictates it.
    } catch (e) {
      console.error('Approval failed:', e);
      addMessage({
        messageId: crypto.randomUUID(),
        senderType: 'SYSTEM_NOTICE',
        content: '승인 요청에 실패했습니다.',
        createdAt: new Date().toISOString()
      });
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 shrink-0">
        <div className="flex items-center gap-2">
          {/* Icon placeholder */}
          <div className="w-3 h-4 bg-blue-400 rounded-sm opacity-80" />
          <h2 className="text-slate-200 text-base font-medium">Tool Generation Plan</h2>
        </div>
        <div className="px-2 py-1 bg-blue-400/10 border border-blue-400/20 rounded text-[10px] text-blue-400 font-medium">
          {currentPlan ? `V ${currentPlan.version}` : 'DRAFT'}
        </div>
      </div>

      {/* Progress Section */}
      <div className="bg-[#0d1c2d] border border-slate-700/50 rounded-lg p-4 mb-8 shrink-0">
        <div className="flex justify-between items-end mb-4">
          <div>
            <div className="text-[10px] text-slate-500 tracking-wider mb-1">CURRENT STAGE</div>
            <div className="text-sm text-blue-100 font-medium">
              {progressInfo?.step || '준비 중'}
            </div>
          </div>
          <div className="text-xl text-blue-400 font-medium">
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

      {/* Step / Plan List */}
      <div className="flex-1 overflow-y-auto pr-2 space-y-4 -mr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {currentPlan ? (
          currentPlan.blocks.map(block => (
            <div key={block.blockId} className="bg-slate-800/30 border border-slate-700/50 p-4 rounded text-sm text-slate-300 flex flex-col gap-3">
              <div>
                <div className="font-medium text-blue-200 mb-1">{block.title}</div>
                <div className="text-slate-400 leading-relaxed whitespace-pre-wrap">{block.content}</div>
              </div>
              
              {commentMode && (
                <div className="mt-2">
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
          <div className="text-center text-slate-500 text-sm mt-10">
            AI가 계획을 생성하면 여기에 표시됩니다.
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="pt-8 shrink-0 space-y-3">
        <button 
          onClick={handleApprove}
          disabled={draftPhase !== 'REVIEW' || commentMode || isApproving || isGenerating || isClosed}
          className="w-full bg-blue-400 hover:bg-blue-500 text-[#00315d] font-bold py-3 rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isClosed ? '종료된 세션' : isApproving ? '승인 요청 중...' : '생성 승인'}
        </button>
        <button 
          disabled={draftPhase !== 'REVIEW' || isGenerating || isApproving || isClosed}
          onClick={handleRequestFeedbackClick}
          className={`w-full border py-3 rounded text-sm transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed
            ${commentMode 
              ? 'bg-blue-500 text-white border-blue-500 hover:bg-blue-600' 
              : 'border-slate-500 text-blue-100 hover:bg-slate-800'
            }`}
        >
          {commentMode ? '수정 요청 보내기' : '수정 요청'}
        </button>
      </div>
    </div>
  );
}
