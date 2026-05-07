import { useState, useRef, useEffect } from 'react';
import type { KeyboardEvent } from 'react';
import { useParams } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';

import { useProjectStore } from '../../stores/useProjectStore';

export function ChatArea() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const { currentProject } = useProjectStore();
  const {
    messages,
    addMessage,
    updateLastMessageContent,
    isGenerating,
    setIsGenerating,
    setAbortController,
    currentToolId,
    setPlan,
    setProgressInfo,
    title,
    isClosed
  } = useChatSessionStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const handleSend = () => {
    if (!input.trim() || isGenerating || !projectId || !sessionId) return;

    const userMessage = input.trim();
    setInput('');
    setIsGenerating(true);

    // 사용자 메시지 추가
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'USER',
      content: userMessage,
      createdAt: new Date().toISOString()
    });

    // 어시스턴트 임시 메시지 추가
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'ASSISTANT',
      content: '',
      createdAt: new Date().toISOString()
    });

    const abortCtrl = chatApi.generateToolStream(
      projectId,
      sessionId,
      currentToolId,
      { message: userMessage },
      (ev: unknown) => {
        try {
          const event = ev as { data?: string };
          const data = event.data ? JSON.parse(event.data) : null;
          if (!data) return;

          // 임의의 SSE 규격 적용
          if (data.type === 'chunk' && data.content) {
            updateLastMessageContent(data.content);
          } else if (data.type === 'plan') {
            setPlan(data.plan);
          } else if (data.type === 'progress') {
            setProgressInfo(data.progress);
          }
        } catch {
          // JSON 파싱 실패 시 일반 텍스트로 간주하여 처리 (또는 무시)
          const event = ev as { data?: string };
          if (event.data) {
            updateLastMessageContent(event.data);
          }
        }
      },
      (err) => {
        console.error('SSE Error:', err);
        setIsGenerating(false);
        setAbortController(null);
      },
      () => {
        setIsGenerating(false);
        setAbortController(null);
      }
    );

    setAbortController(abortCtrl);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full relative">
      {/* Background Grid Effect */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-20 pointer-events-none" />

      {/* Top App Bar (Workspace Info) */}
      <div className="h-14 border-b border-slate-800 bg-[#0b0e14]/60 backdrop-blur flex items-center justify-between px-6 z-20">
        <div className="flex items-center gap-1">
          <span className="text-base font-bold text-blue-400 uppercase tracking-wider">{currentProject?.projectName || 'Loading...'}</span>
          <span className="mx-1.5 text-slate-600">/</span>
          <span className="text-sm font-medium text-slate-400">{title || '새 세션'}</span>
          {isClosed && (
            <div className="ml-3 flex items-center gap-1.5 px-2 py-0.5 bg-red-500/10 border border-red-500/20 rounded text-[10px] text-red-400 font-bold uppercase tracking-wider">
              <Lock size={10} />
              Closed
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-8 z-10 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {messages.length > 0 ? (
          <div className="space-y-6">
            {messages.map(msg => (
              <div key={msg.messageId} className={`flex ${msg.senderType === 'USER' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] p-4 rounded-lg whitespace-pre-wrap ${msg.senderType === 'USER'
                  ? 'bg-[#3e495d] text-[#aeb9d0]'
                  : msg.senderType === 'SYSTEM_NOTICE' || msg.senderType === 'SYSTEM'
                    ? 'bg-slate-800/50 border border-slate-700 text-slate-400 text-xs italic text-center mx-auto'
                    : 'bg-[#1c2b3c] border-l-2 border-[#a4c9ff] text-[#d4e4fa]'
                  }`}>
                  {msg.content || (isGenerating && msg.senderType === 'ASSISTANT' ? '생성 중...' : '')}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="text-slate-500 flex justify-center items-center h-full">
            새로운 지시를 내려 AI와 대화를 시작하세요.
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="px-8 pb-8 pt-4 bg-gradient-to-t from-[#051424] via-[#051424]/90 to-transparent z-10">
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
                  : 'AI에게 다음 작업을 지시하세요... (Enter로 전송, Shift+Enter로 줄바꿈)'
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


