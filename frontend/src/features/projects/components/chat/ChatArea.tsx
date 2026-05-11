import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useParams } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { toast } from 'sonner';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';
import { useToolGenerationSSE } from '../../hooks/useToolGenerationSSE';
import { useProjectStore } from '../../stores/useProjectStore';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import { TypingIndicator } from '@/components/ui/TypingIndicator';
import { ToolPlanMode } from '../../types/chat';
import type { ToolPlanMode as ToolPlanModeType } from '../../types/chat';

const MODE_OPTIONS: Array<{ value: ToolPlanModeType; label: string; description: string }> = [
  { value: ToolPlanMode.ASK, label: 'ASK', description: '일반 대화' },
  { value: ToolPlanMode.PLAN, label: 'PLAN', description: '도구 명세' },
  { value: ToolPlanMode.AGENT, label: 'AGENT', description: '실행 준비' },
];

export function ChatArea() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const { currentProject } = useProjectStore();
  const {
    messages,
    mode,
    addMessage,
    isGenerating,
    setIsGenerating,
    currentToolPlanId,
    draftPhase,
    title,
    isClosed,
    planVersion,
    setMode,
    setCurrentRunId,
    setDraftPhase,
    setPlanStatus,
    setCurrentPlan,
  } = useChatSessionStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { connectSSE } = useToolGenerationSSE();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const appendUserMessage = (content: string) => {
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'USER',
      messageType: mode === ToolPlanMode.PLAN ? 'TOOL_PLAN_REQUEST' : 'CHAT',
      contentType: 'TEXT',
      content,
      createdAt: new Date().toISOString()
    });
  };

  const appendAssistantPlaceholder = () => {
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'ASSISTANT',
      messageType: 'TOOL_PLAN_RESPONSE',
      contentType: 'MARKDOWN',
      content: '',
      createdAt: new Date().toISOString()
    });
  };

  const sendAskMessage = async (userMessage: string) => {
    appendUserMessage(userMessage);
    await chatApi.createMessage(projectId!, sessionId!, userMessage);
    toast.info('ASK 메시지를 저장했습니다. AI 응답 스트림은 후속 연동 대상입니다.');
  };

  const sendPlanMessage = async (userMessage: string) => {
    appendUserMessage(userMessage);
    appendAssistantPlaceholder();
    setIsGenerating(true);
    setDraftPhase('PLAN');
    setPlanStatus('REQUESTED');
    setCurrentPlan(null);

    const regeneratableToolPlanId = (draftPhase === 'REVIEW' || draftPhase === 'REJECTED')
      ? currentToolPlanId
      : null;
    const result = regeneratableToolPlanId
      ? await chatApi.regenerateToolPlan(
        projectId!,
        sessionId!,
        regeneratableToolPlanId,
        {
          basePlanVersion: planVersion,
          feedbackItems: [{ blockId: 'general-feedback', comment: userMessage }],
          mode: ToolPlanMode.PLAN
        }
      )
      : await chatApi.generateToolPlan(
        projectId!,
        sessionId!,
        { userMessage, mode: ToolPlanMode.PLAN }
      );

    setCurrentRunId(result.runId);
    setPlanStatus(result.status);
    connectSSE(result.sseUrl, 'PLAN', result.runId);
  };

  const handleSend = async () => {
    if (!input.trim() || isGenerating || !projectId || !sessionId) return;

    const userMessage = input.trim();
    setInput('');

    try {
      if (mode === ToolPlanMode.ASK) {
        await sendAskMessage(userMessage);
        return;
      }

      if (mode === ToolPlanMode.AGENT) {
        toast.info('AGENT 모드는 Tool 실행 계약 확정 후 연결됩니다.');
        return;
      }

      await sendPlanMessage(userMessage);
    } catch (err) {
      console.error('Chat request failed:', err);
      setIsGenerating(false);
      toast.error('요청 처리에 실패했습니다.');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-20 pointer-events-none" />

      <div className="h-14 border-b border-slate-800 bg-[#0b0e14]/60 backdrop-blur flex items-center justify-between px-6 z-20">
        <div className="flex items-center gap-1">
          <span className="text-base font-bold text-blue-400 uppercase tracking-wider">{currentProject?.projectName || 'Loading...'}</span>
          <span className="mx-1.5 text-slate-600">/</span>
          <span className="text-sm font-medium text-slate-400">{title || '대화 세션'}</span>
          {isClosed && (
            <div className="ml-3 flex items-center gap-1.5 px-2 py-0.5 bg-red-500/10 border border-red-500/20 rounded text-[10px] text-red-400 font-bold uppercase tracking-wider">
              <Lock size={10} />
              Closed
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8 z-10 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {messages.length > 0 ? (
          <div className="space-y-6">
            {messages.map(msg => (
              <div key={msg.messageId} className={`flex ${msg.senderType === 'USER' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] p-4 rounded-lg overflow-x-auto ${msg.senderType === 'USER'
                  ? 'bg-[#3e495d] text-[#aeb9d0]'
                  : msg.senderType === 'SYSTEM_NOTICE' || msg.senderType === 'SYSTEM'
                    ? 'bg-slate-800/50 border border-slate-700 text-slate-400 text-xs italic text-center mx-auto'
                    : 'bg-[#1c2b3c] border-l-2 border-[#a4c9ff] text-[#d4e4fa] w-full'
                  }`}>
                  {msg.senderType === 'ASSISTANT' ? (
                    msg.content ? <MarkdownViewer content={msg.content} /> : (isGenerating ? <TypingIndicator /> : '')
                  ) : (
                    <div className="whitespace-pre-wrap leading-relaxed text-[15px] break-words">{msg.content}</div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="text-slate-500 flex justify-center items-center h-full">
            모드를 선택하고 대화를 시작하세요.
          </div>
        )}
      </div>

      <div className="px-8 pb-8 pt-4 bg-gradient-to-t from-[#051424] via-[#051424]/90 to-transparent z-10">
        <div className="mb-3 flex gap-2">
          {MODE_OPTIONS.map(option => (
            <button
              key={option.value}
              type="button"
              disabled={isGenerating || isClosed || option.value === ToolPlanMode.AGENT}
              onClick={() => setMode(option.value)}
              className={`px-3 py-2 rounded border text-xs font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                mode === option.value
                  ? 'bg-blue-400 border-blue-400 text-slate-950'
                  : 'bg-[#0d1c2d] border-slate-700 text-slate-400 hover:text-blue-200 hover:border-blue-400/50'
              }`}
              title={option.description}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className={`bg-[#0d1c2d] border ${isGenerating ? 'border-slate-600' : isClosed ? 'border-red-900/30' : 'border-slate-700/50'} rounded-lg p-3 flex items-end shadow-lg shadow-blue-500/5 transition-colors`}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating || isClosed}
            className="flex-1 bg-transparent border-none outline-none resize-none px-3 py-2 text-sm text-slate-300 placeholder-slate-500 min-h-[40px] max-h-[200px] disabled:opacity-50"
            rows={1}
            placeholder={
              isGenerating
                ? 'AI가 작업 중입니다...'
                : isClosed
                  ? '종료된 세션입니다. 새로운 세션을 시작해 주세요.'
                  : mode === ToolPlanMode.ASK
                    ? '일반 질문을 입력하세요. (Enter 전송, Shift+Enter 줄바꿈)'
                    : 'Tool PLAN 요청 또는 피드백을 입력하세요. (Enter 전송, Shift+Enter 줄바꿈)'
            }
          />
          <button
            onClick={handleSend}
            disabled={isGenerating || !input.trim() || isClosed}
            className="bg-blue-400 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-slate-900 px-6 py-2 rounded text-xs font-bold transition-colors ml-4 uppercase tracking-wider"
          >
            {isGenerating ? '처리중' : '보내기'}
          </button>
        </div>
      </div>
    </div>
  );
}
