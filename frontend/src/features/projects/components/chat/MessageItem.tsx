import { useState } from 'react';
import { Copy, Check, CheckCircle, Play, CheckCircle2, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import type { ChatMessage, ToolExecutionNotice, ToolExecutionNoticeGroup } from '../../types/chat';

interface MessageItemProps {
  msg: ChatMessage;
  isLast: boolean;
  isGenerating: boolean;
  isLoadingDots: boolean;
}

function getToolExecutionState(notice: ToolExecutionNotice): 'started' | 'completed' | 'failed' {
  if (notice.noticeType === 'TOOL_EXECUTION_FAILED' || notice.isError === true) return 'failed';
  if (notice.noticeType === 'TOOL_EXECUTION_COMPLETED') return 'completed';
  return 'started';
}

function ToolExecutionStatusIcon({ state }: { state: 'started' | 'completed' | 'failed' }) {
  return (
    <div className={`p-1.5 rounded-md shrink-0 ${state === 'started' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
        state === 'completed' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
          'bg-red-500/10 text-red-400 border border-red-500/20'
      }`}>
      {state === 'started' && <Play className="w-3.5 h-3.5 animate-pulse" />}
      {state === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
      {state === 'failed' && <AlertTriangle className="w-3.5 h-3.5" />}
    </div>
  );
}

function ToolExecutionNoticeView({ notice, compact = false }: { notice: ToolExecutionNotice; compact?: boolean }) {
  const [isOpen, setIsOpen] = useState(false);
  const executionState = getToolExecutionState(notice);
  const isStarted = executionState === 'started';
  const isFailed = executionState === 'failed';
  const isCompleted = executionState === 'completed';
  const errorOutput = notice.error || notice.output;

  return (
    <div className="flex flex-col gap-2 w-full text-slate-300 font-sans">
      <div className={`flex items-center justify-between gap-3 rounded-lg bg-slate-900/60 border border-slate-800/80 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)] ${compact ? 'p-2' : 'p-3'}`}>
        <div className="flex items-center gap-2.5 min-w-0">
          <ToolExecutionStatusIcon state={executionState} />
          <div className="flex flex-col min-w-0">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-bold font-['Space_Grotesk']">
              {isStarted ? 'Tool Execution Started' : isCompleted ? 'Tool Execution Completed' : 'Tool Execution Failed'}
            </span>
            <span className="text-xs font-bold text-slate-200 truncate">
              도구 호출: <code className="text-blue-400 px-1 py-0.5 bg-blue-950/40 rounded border border-blue-800/30 text-[11px] font-mono">{notice.toolName}</code>
            </span>
          </div>
        </div>

        {(notice.toolInput || notice.output || notice.error) && (
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-slate-200 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 rounded px-2 py-1 cursor-pointer transition-all active:scale-95 shrink-0"
          >
            <span>{isOpen ? 'Close' : 'Details'}</span>
            {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
      </div>

      {isOpen && (
        <div className="flex flex-col gap-2.5 p-3 rounded-lg bg-[#0c1322] border border-slate-800/80 animate-fade-in font-mono text-[11px] leading-relaxed max-w-full overflow-hidden shadow-[inset_0_2px_4px_rgba(0,0,0,0.4)]">
          {notice.toolInput && (
            <div className="flex flex-col gap-1 max-w-full">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold">Input Arguments</span>
              <pre className="p-2 rounded bg-slate-950/40 text-blue-300 border border-slate-900/60 overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(notice.toolInput, null, 2)}
              </pre>
            </div>
          )}

          {isCompleted && notice.output && (
            <div className="flex flex-col gap-1 max-w-full">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold">Execution Output</span>
              <pre className="p-2 rounded bg-slate-950/40 text-slate-400 border border-slate-900/60 overflow-x-auto max-h-[250px] overflow-y-auto whitespace-pre-wrap break-all">
                {notice.output}
              </pre>
            </div>
          )}

          {isFailed && errorOutput && (
            <div className="flex flex-col gap-1 max-w-full">
              <span className="text-[9px] text-red-400/80 uppercase tracking-wider font-bold">Error Output</span>
              <pre className="p-2 rounded bg-red-950/10 text-red-300 border border-red-950/20 overflow-x-auto whitespace-pre-wrap break-all">
                {errorOutput}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolExecutionGroupView({ group }: { group: ToolExecutionNoticeGroup }) {
  const [isOpen, setIsOpen] = useState(false);
  const failedCount = group.notices.filter((notice) => getToolExecutionState(notice) === 'failed').length;
  const runningCount = group.notices.filter((notice) => getToolExecutionState(notice) === 'started').length;
  const completedCount = group.notices.filter((notice) => getToolExecutionState(notice) === 'completed').length;
  const groupState = failedCount > 0 ? 'failed' : runningCount > 0 ? 'started' : 'completed';
  const summaryParts = [
    runningCount > 0 ? `${runningCount} running` : null,
    completedCount > 0 ? `${completedCount} completed` : null,
    failedCount > 0 ? `${failedCount} failed` : null,
  ].filter(Boolean);

  return (
    <div className="flex flex-col gap-2 w-full text-slate-300 font-sans">
      <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)]">
        <div className="flex items-center gap-2.5 min-w-0">
          <ToolExecutionStatusIcon state={groupState} />
          <div className="flex flex-col min-w-0">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-bold font-['Space_Grotesk']">
              Tool Executions
            </span>
            <span className="text-xs font-bold text-slate-200 truncate">
              도구 실행 {group.notices.length}개 · {summaryParts.join(' · ')}
            </span>
          </div>
        </div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-slate-200 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 rounded px-2 py-1 cursor-pointer transition-all active:scale-95 shrink-0"
        >
          <span>{isOpen ? 'Close' : 'Details'}</span>
          {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {!isOpen && (
        <div className="flex flex-wrap gap-1.5">
          {group.notices.map((notice, index) => {
            const state = getToolExecutionState(notice);
            return (
              <span
                key={`${notice.toolUseId || notice.toolName}-${index}`}
                className={`rounded border px-2 py-1 text-[10px] font-mono ${state === 'started'
                    ? 'border-blue-500/20 bg-blue-500/10 text-blue-300'
                    : state === 'completed'
                      ? 'border-green-500/20 bg-green-500/10 text-green-300'
                      : 'border-red-500/20 bg-red-500/10 text-red-300'
                  }`}
              >
                {notice.toolName}: {state}
              </span>
            );
          })}
        </div>
      )}

      {isOpen && (
        <div className="flex flex-col gap-2 rounded-lg bg-[#0c1322] border border-slate-800/80 p-2">
          {group.notices.map((notice, index) => (
            <ToolExecutionNoticeView
              key={`${notice.toolUseId || notice.toolName}-${index}`}
              notice={notice}
              compact
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function MessageItem({ msg, isLoadingDots }: MessageItemProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const isToolNotice = (() => {
    if (msg.content.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(msg.content);
        return !!(
          parsed.noticeType === 'TOOL_EXECUTION_GROUP'
          || (parsed.noticeType && parsed.noticeType.startsWith('TOOL_EXECUTION_'))
        );
      } catch {
        return false;
      }
    }
    return false;
  })();

  const isMessageLoading = msg.senderType === 'ASSISTANT' && !msg.content.trim();

  const renderContent = () => {
    if (msg.senderType === 'ASSISTANT') {
      if (isMessageLoading) {
        return (
          <div className="flex items-center gap-1.5 py-2 px-1">
            <div className="w-1.5 h-1.5 bg-blue-400/60 rounded-full animate-bounce" />
            <div className="w-1.5 h-1.5 bg-blue-400/60 rounded-full animate-bounce [animation-delay:0.2s]" />
            <div className="w-1.5 h-1.5 bg-blue-400/60 rounded-full animate-bounce [animation-delay:0.4s]" />
          </div>
        );
      }
      return <MarkdownViewer content={msg.content} />;
    }

    if (msg.content.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(msg.content);

        if (parsed.noticeType === 'TOOL_EXECUTION_GROUP' && Array.isArray(parsed.notices)) {
          return <ToolExecutionGroupView group={parsed as ToolExecutionNoticeGroup} />;
        }

        if (parsed.noticeType && parsed.noticeType.startsWith('TOOL_EXECUTION_')) {
          const notice = parsed as ToolExecutionNotice;
          return <ToolExecutionNoticeView notice={notice} />;
        }

        if (parsed.feedbackItems && Array.isArray(parsed.feedbackItems)) {
          return (
            <div className="space-y-1">
              <div className="font-bold text-blue-300 mb-1 text-xs uppercase tracking-tight">PLAN 수정 요청</div>
              {parsed.feedbackItems.map((item: { comment: string }, i: number) => (
                <div key={i} className="flex gap-2 text-[14px]">
                  <span className="text-blue-400/60 mt-1">•</span>
                  <span>{item.comment}</span>
                </div>
              ))}
            </div>
          );
        }

        if (parsed.toolApprovalId) {
          return (
            <div className="flex flex-col gap-1.5">
              <div className="font-bold text-blue-300 text-xs uppercase tracking-tight">도구 생성 요청</div>
              <div className="text-[14px] flex items-center gap-2 text-slate-300">
                <CheckCircle className="w-3.5 h-3.5 text-blue-400" />
                <span>도구 생성을 요청했습니다</span>
              </div>
            </div>
          );
        }

        if (parsed.status === 'BUILT') {
          return (
            <div className="flex flex-col gap-1.5">
              <div className="font-bold text-green-400 text-xs uppercase tracking-tight">도구 생성 완료</div>
              <div className="text-[14px] flex items-center gap-2 text-slate-300">
                <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                <span>도구(<code>{parsed.fileName}</code>)가 성공적으로 생성되었습니다.</span>
              </div>
            </div>
          );
        }
      } catch {
        // JSON 파싱 실패 시 일반 텍스트로 렌더링
      }
    }

    return <div className="whitespace-pre-wrap leading-relaxed text-[15px] break-words">{msg.content}</div>;
  };

  const showCopyButton = msg.content && !isLoadingDots && !isMessageLoading && (msg.senderType === 'USER' || msg.senderType === 'ASSISTANT');

  return (
    <div className={`flex ${msg.senderType === 'USER' ? 'justify-end' : 'justify-start'}`}>
      <div className={`relative group max-w-[75%] ${isLoadingDots || isMessageLoading ? 'px-4 py-2' : 'p-4'} rounded-lg overflow-x-auto ${msg.senderType === 'USER'
          ? 'bg-slate-700 text-slate-100 shadow-md'
          : isToolNotice
            ? 'bg-slate-900/30 border border-slate-800/60 text-slate-300 w-full shadow-lg'
            : msg.senderType === 'SYSTEM_NOTICE' || msg.senderType === 'SYSTEM'
              ? 'bg-slate-800/50 border border-slate-700 text-slate-400 text-xs italic text-center mx-auto'
              : `bg-[#1c2b3c] border-l-2 border-[#a4c9ff] text-[#d4e4fa] ${isLoadingDots || isMessageLoading ? 'w-fit' : 'w-full'}`
        }`}>

        {showCopyButton && (
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 p-1.5 rounded bg-slate-800/50 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity hover:text-slate-100 hover:bg-slate-700"
            title="복사하기"
          >
            {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
          </button>
        )}

        {renderContent()}
      </div>
    </div>
  );
}
