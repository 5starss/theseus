import { useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { toast } from 'sonner';
import { useChatSessionStore } from '../../stores/useChatSessionStore';
import { chatApi } from '../../api/chat';
import { remoteWorkspaceApi } from '../../api/remoteWorkspace';
import { useToolGenerationSSE } from '../../hooks/useToolGenerationSSE';
import { useChatStreamSSE } from '../../hooks/useChatStreamSSE';
import { useProjectStore } from '../../stores/useProjectStore';
import { MessageItem } from './MessageItem';
import { ToolPlanMode } from '../../types/chat';
import type { ChatMessage, ToolExecutionNotice, ToolExecutionNoticeGroup, ToolPlanMode as ToolPlanModeType } from '../../types/chat';
import type { RemoteWorkspaceResponse } from '../../types/project';

const MODE_OPTIONS: Array<{ value: ToolPlanModeType; label: string; description: string }> = [
  { value: ToolPlanMode.ASK, label: 'ASK', description: '일반 대화' },
  { value: ToolPlanMode.PLAN, label: 'PLAN', description: '도구 명세' },
  { value: ToolPlanMode.AGENT, label: 'AGENT', description: '실행 준비' },
];

function parseToolExecutionNotice(content: string): ToolExecutionNotice | null {
  const trimmed = content.trim();
  if (!trimmed.startsWith('{')) return null;

  try {
    const parsed = JSON.parse(trimmed) as Partial<ToolExecutionNotice>;
    if (
      typeof parsed.noticeType === 'string'
      && parsed.noticeType.startsWith('TOOL_EXECUTION_')
      && typeof parsed.toolName === 'string'
    ) {
      return parsed as ToolExecutionNotice;
    }
  } catch {
    return null;
  }

  return null;
}

function toolNoticeExactKey(notice: ToolExecutionNotice): string | null {
  return notice.toolUseId ? `id:${notice.toolUseId}` : null;
}

function toolNoticeNameKey(notice: ToolExecutionNotice): string | null {
  return notice.toolName ? `tool:${notice.toolName}` : null;
}

function isTerminalToolNotice(notice: ToolExecutionNotice): boolean {
  return notice.noticeType !== 'TOOL_EXECUTION_STARTED' || notice.isError === true;
}

function dedupeToolExecutionMessages(messages: ChatMessage[]): ChatMessage[] {
  const visible: ChatMessage[] = [];
  const noticeIndexByExactKey = new Map<string, number>();
  const startedIndexesByToolName = new Map<string, number[]>();

  const rememberStarted = (notice: ToolExecutionNotice, visibleIndex: number) => {
    const nameKey = toolNoticeNameKey(notice);
    if (!nameKey) return;
    const indexes = startedIndexesByToolName.get(nameKey) || [];
    indexes.push(visibleIndex);
    startedIndexesByToolName.set(nameKey, indexes);
  };

  const takeLatestStartedIndex = (notice: ToolExecutionNotice): number | null => {
    const nameKey = toolNoticeNameKey(notice);
    if (!nameKey) return null;

    const indexes = startedIndexesByToolName.get(nameKey);
    if (!indexes) return null;

    while (indexes.length > 0) {
      const index = indexes.pop();
      if (index === undefined) break;

      const existingNotice = parseToolExecutionNotice(visible[index]?.content || '');
      if (existingNotice && !isTerminalToolNotice(existingNotice)) {
        return index;
      }
    }

    return null;
  };

  for (const message of messages) {
    const notice = parseToolExecutionNotice(message.content);
    const exactKey = notice ? toolNoticeExactKey(notice) : null;

    if (!notice) {
      visible.push(message);
      continue;
    }

    if (!isTerminalToolNotice(notice)) {
      const existingIndex = exactKey ? noticeIndexByExactKey.get(exactKey) : undefined;
      if (existingIndex !== undefined) {
        const existingNotice = parseToolExecutionNotice(visible[existingIndex].content);
        if (!existingNotice || !isTerminalToolNotice(existingNotice)) {
          visible[existingIndex] = message;
        }
        continue;
      }

      const visibleIndex = visible.length;
      visible.push(message);
      if (exactKey) {
        noticeIndexByExactKey.set(exactKey, visibleIndex);
      }
      rememberStarted(notice, visibleIndex);
      continue;
    }

    const exactMatchIndex = exactKey ? noticeIndexByExactKey.get(exactKey) : undefined;
    const fallbackStartedIndex = exactMatchIndex === undefined ? takeLatestStartedIndex(notice) : null;
    const replaceIndex = exactMatchIndex ?? fallbackStartedIndex;

    if (replaceIndex !== undefined && replaceIndex !== null) {
      visible[replaceIndex] = message;
      if (exactKey) {
        noticeIndexByExactKey.set(exactKey, replaceIndex);
      }
      continue;
    }

    const visibleIndex = visible.length;
    visible.push(message);
    if (exactKey) {
      noticeIndexByExactKey.set(exactKey, visibleIndex);
    }
  }

  return visible;
}

function isToolExecutionMessage(message: ChatMessage): boolean {
  return parseToolExecutionNotice(message.content) !== null;
}

function groupToolExecutionMessages(messages: ChatMessage[]): ChatMessage[] {
  const grouped: ChatMessage[] = [];
  let buffer: ChatMessage[] = [];

  const flushBuffer = () => {
    if (buffer.length === 0) return;

    if (buffer.length === 1) {
      grouped.push(buffer[0]);
      buffer = [];
      return;
    }

    const notices = buffer
      .map((message) => parseToolExecutionNotice(message.content))
      .filter((notice): notice is ToolExecutionNotice => notice !== null);
    const groupPayload: ToolExecutionNoticeGroup = {
      noticeType: 'TOOL_EXECUTION_GROUP',
      notices,
    };
    grouped.push({
      ...buffer[0],
      messageId: `tool-execution-group-${buffer[0].messageId}-${buffer[buffer.length - 1].messageId}`,
      senderType: 'SYSTEM_NOTICE',
      messageType: 'SYSTEM_NOTICE',
      contentType: 'JSON',
      content: JSON.stringify(groupPayload),
    });
    buffer = [];
  };

  for (const message of messages) {
    if (isToolExecutionMessage(message)) {
      buffer.push(message);
      continue;
    }

    flushBuffer();
    grouped.push(message);
  }

  flushBuffer();

  return grouped;
}

export function ChatArea() {
  const { projectId, sessionId } = useParams<{ projectId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { currentProject } = useProjectStore();
  const {
    messages,
    mode,
    addMessage,
    isGenerating,
    setIsGenerating,
    isBuilding,
    progressInfo,
    title,
    isClosed,
    selectedRemoteWorkspaceId,
    setMode,
    setCurrentRunId,
    setDraftPhase,
    setPlanStatus,
    setCurrentPlan,
    setSelectedRemoteWorkspaceId,
  } = useChatSessionStore();

  const [input, setInput] = useState('');
  const [remoteWorkspaces, setRemoteWorkspaces] = useState<RemoteWorkspaceResponse[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isAtBottom = useRef(true);

  const { connectSSE } = useToolGenerationSSE();
  const { connectChatStream } = useChatStreamSSE();
  const selectedRemoteWorkspace = remoteWorkspaces.find(
    workspace => workspace.remoteWorkspaceId === selectedRemoteWorkspaceId
  );
  const processingLogText = (
    messages[messages.length - 1]?.content
    || progressInfo?.message
    || 'Initializing stream...'
  ).replace(/blockId:\s*[\w-]+\s*/gi, '');
  const showProcessingPanel = (isGenerating || isBuilding) && (
    mode === ToolPlanMode.PLAN || Boolean(progressInfo?.step || progressInfo?.message)
  );
  const processingPanelTitle = isBuilding
    ? 'Tool Building'
    : (progressInfo?.step || `${mode} Processing`);
  const visibleMessages = useMemo(
    () => groupToolExecutionMessages(dedupeToolExecutionMessages(messages)),
    [messages]
  );

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    // 하단에서 100px 이내면 바닥에 있는 것으로 간주
    const atBottom = scrollHeight - scrollTop - clientHeight < 100;
    isAtBottom.current = atBottom;
  };

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    if (isAtBottom.current) {
      scrollToBottom(isGenerating ? 'auto' : 'smooth');
    }
  }, [messages, isGenerating, progressInfo]);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;
    const fetchRemoteWorkspaces = async () => {
      try {
        const responses = await remoteWorkspaceApi.getRemoteWorkspaces(projectId);
        if (cancelled) return;

        setRemoteWorkspaces(responses);
        const hasSelectedWorkspace = responses.some(
          workspace => workspace.remoteWorkspaceId === selectedRemoteWorkspaceId
        );
        if (selectedRemoteWorkspaceId && !hasSelectedWorkspace) {
          setSelectedRemoteWorkspaceId(null);
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Failed to load remote workspaces', error);
        }
      }
    };

    void fetchRemoteWorkspaces();
    return () => {
      cancelled = true;
    };
  }, [projectId, selectedRemoteWorkspaceId, setSelectedRemoteWorkspaceId]);

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

  const appendAssistantPlaceholder = (messageType: ChatMessage['messageType'] = 'TOOL_PLAN_RESPONSE') => {
    addMessage({
      messageId: crypto.randomUUID(),
      senderType: 'ASSISTANT',
      messageType,
      contentType: 'MARKDOWN',
      content: '',
      createdAt: new Date().toISOString()
    });
  };

  const sendChatStreamMessage = (userMessage: string, streamMode: Extract<ToolPlanModeType, 'ASK' | 'AGENT'>) => {
    appendUserMessage(userMessage);
    appendAssistantPlaceholder('CHAT');
    setIsGenerating(true);
    setDraftPhase(null);
    setPlanStatus(null);
    setCurrentPlan(null);
    connectChatStream(
      projectId!,
      sessionId!,
      streamMode,
      userMessage,
      selectedRemoteWorkspaceId ?? undefined
    );
  };

  const sendPlanMessage = async (userMessage: string) => {
    appendUserMessage(userMessage);
    appendAssistantPlaceholder();
    setIsGenerating(true);
    setDraftPhase('PLAN');
    setPlanStatus('REQUESTED');
    setCurrentPlan(null);

    const result = await chatApi.generateToolPlan(
      projectId!,
      sessionId!,
      {
        userMessage,
        mode: ToolPlanMode.PLAN,
        remoteWorkspaceId: selectedRemoteWorkspaceId ?? undefined
      }
    );

    setCurrentRunId(result.runId);
    setPlanStatus(result.status);
    connectSSE(result.sseUrl, 'PLAN', result.runId);
  };

  const handleSend = async () => {
    if (!input.trim() || isGenerating || !projectId || !sessionId) return;

    const userMessage = input.trim();
    setInput('');
    isAtBottom.current = true;

    try {
      if (mode === ToolPlanMode.ASK) {
        sendChatStreamMessage(userMessage, ToolPlanMode.ASK);
        return;
      }

      if (mode === ToolPlanMode.AGENT) {
        sendChatStreamMessage(userMessage, ToolPlanMode.AGENT);
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

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-8 z-10 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent"
      >
        {messages.length > 0 ? (
          <div className="space-y-6">
            {visibleMessages.map((msg, idx) => {
              const isLast = idx === visibleMessages.length - 1;

              // 최신 생성 중인 어시스턴트 메시지는 말풍선 리스트에서 숨김 (별도 로그 UI로 표시)
              const isLastAssistant = msg.senderType === 'ASSISTANT' && isLast;
              if (isLastAssistant && (isGenerating || isBuilding) && mode === ToolPlanMode.PLAN) return null;

              const isLoadingDots = msg.senderType === 'ASSISTANT' && isLast && isGenerating && !msg.content;

              return (
                <MessageItem
                  key={msg.messageId}
                  msg={msg}
                  isLast={isLast}
                  isGenerating={isGenerating}
                  isLoadingDots={isLoadingDots}
                />
              );
            })}

            {/* 별도의 생성 로그 UI (말풍선과 별개) */}
            {showProcessingPanel && (
              <div className="flex justify-start animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="w-full max-w-[85%] bg-slate-900/40 border border-blue-500/20 rounded-xl overflow-hidden shadow-2xl backdrop-blur-sm">
                  <div className="bg-blue-500/10 px-4 py-2 border-b border-blue-500/10 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce" />
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:0.2s]" />
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:0.4s]" />
                      </div>
                      <span className="text-[10px] font-bold text-blue-400 uppercase tracking-[0.2em]">
                        {processingPanelTitle}
                      </span>
                    </div>
                  </div>
                  <div className="p-4 space-y-3">
                    {progressInfo?.message && (
                      <div className="text-sm text-blue-100/90 font-medium leading-relaxed">
                        {progressInfo.message}
                      </div>
                    )}
                    <div className="bg-[#050c18] rounded-lg p-3 border border-slate-800/50">
                      <div className="font-mono text-[11px] leading-relaxed text-slate-400 break-all max-h-[150px] overflow-y-auto scrollbar-none">
                        <span className="text-blue-500/50 mr-2">$</span>
                        {processingLogText}
                        <span className="inline-block w-1.5 h-3.5 bg-blue-500/50 ml-1 animate-pulse" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
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
              disabled={isGenerating || isClosed}
              onClick={() => setMode(option.value)}
              className={`px-3 py-2 rounded border text-xs font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${mode === option.value
                ? 'bg-blue-400 border-blue-400 text-slate-950'
                : 'bg-[#0d1c2d] border-slate-700 text-slate-400 hover:text-blue-200 hover:border-blue-400/50'
                }`}
              title={option.description}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="mb-3 max-w-xs">
          <select
            value={selectedRemoteWorkspaceId ?? ''}
            onChange={(event) => {
              const value = event.target.value;
              setSelectedRemoteWorkspaceId(value ? Number(value) : null);
            }}
            disabled={isGenerating || isClosed}
            className="w-full rounded border border-slate-700 bg-[#0d1c2d] px-3 py-2 text-xs font-medium text-slate-300 outline-none transition-colors focus:border-blue-400/60 disabled:opacity-40"
          >
            <option value="">Remote Workspace 없음</option>
            {remoteWorkspaces.map(workspace => (
              <option key={workspace.remoteWorkspaceId} value={workspace.remoteWorkspaceId}>
                {workspace.name} ({workspace.host})
              </option>
            ))}
          </select>
          {selectedRemoteWorkspace && (
            <p className="mt-2 text-xs text-slate-400">
              {mode === ToolPlanMode.AGENT
                ? selectedRemoteWorkspace.allowWriteExecution
                  ? 'AGENT can use this Remote Workspace for write/command tasks.'
                  : 'This Remote Workspace is read-only for AGENT.'
                : 'ASK/PLAN use the selected Remote Workspace as read-only context.'}
            </p>
          )}
        </div>

        {isClosed ? (
          <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-6 flex flex-col items-center justify-center gap-4 shadow-xl backdrop-blur-sm">
            <div className="flex items-center gap-2 text-red-400 font-medium">
              <Lock size={18} className="animate-pulse" />
              <span className="text-sm tracking-tight">이 세션은 종료되었습니다. 기록만 확인할 수 있습니다.</span>
            </div>
            <button
              onClick={() => navigate(`/projects/${projectId}`, { replace: true })}
              className="bg-blue-400 hover:bg-blue-500 text-slate-900 px-8 py-2.5 rounded font-bold transition-all hover:scale-[1.02] active:scale-[0.98] uppercase tracking-widest text-[11px] shadow-[0_0_20px_rgba(96,165,250,0.3)]"
            >
              새 대화 시작하기
            </button>
          </div>
        ) : (
          <div className={`bg-[#0d1c2d] border ${isGenerating ? 'border-slate-600' : 'border-slate-700/50'} rounded-lg p-3 flex items-end shadow-lg shadow-blue-500/5 transition-colors`}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isGenerating}
              className="flex-1 bg-transparent border-none outline-none resize-none px-3 py-2 text-sm text-slate-300 placeholder-slate-500 min-h-[40px] max-h-[200px] disabled:opacity-50"
              rows={1}
              placeholder={
                isGenerating
                  ? 'AI가 작업 중입니다...'
                  : mode === ToolPlanMode.ASK
                    ? '일반 질문을 입력하세요. (Enter 전송, Shift+Enter 줄바꿈)'
                    : mode === ToolPlanMode.AGENT
                      ? 'Agent에게 승인된 Tool 사용 작업을 지시하세요. (Enter 전송, Shift+Enter 줄바꿈)'
                      : 'Tool PLAN 요청 또는 피드백을 입력하세요. (Enter 전송, Shift+Enter 줄바꿈)'
              }
            />
            <button
              onClick={handleSend}
              disabled={isGenerating || !input.trim()}
              className="bg-blue-400 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-slate-900 px-6 py-2 rounded text-xs font-bold transition-colors ml-4 uppercase tracking-wider"
            >
              {isGenerating ? '처리중' : '보내기'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
