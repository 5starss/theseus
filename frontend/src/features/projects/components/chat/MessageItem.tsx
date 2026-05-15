import { useState } from 'react';
import { Copy, Check, CheckCircle } from 'lucide-react';
import { MarkdownViewer } from '@/components/ui/MarkdownViewer';
import type { ChatMessage } from '../../types/chat';

interface MessageItemProps {
  msg: ChatMessage;
  isLast: boolean;
  isGenerating: boolean;
  isLoadingDots: boolean;
}

export function MessageItem({ msg, isLast, isGenerating, isLoadingDots }: MessageItemProps) {
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

  const renderContent = () => {
    if (msg.senderType === 'ASSISTANT') {
      if (!msg.content && isLast && isGenerating) {
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

    // TOOL_FEEDBACK 타입이거나 내용이 JSON 형태인 경우 파싱 시도
    if (msg.messageType === 'TOOL_FEEDBACK' || msg.content.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(msg.content);
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

  const showCopyButton = msg.content && !isLoadingDots && (msg.senderType === 'USER' || msg.senderType === 'ASSISTANT');

  return (
    <div className={`flex ${msg.senderType === 'USER' ? 'justify-end' : 'justify-start'}`}>
      <div className={`relative group max-w-[70%] ${isLoadingDots ? 'px-4 py-2' : 'p-4'} rounded-lg overflow-x-auto ${msg.senderType === 'USER'
        ? 'bg-slate-700 text-slate-100 shadow-md'
        : msg.senderType === 'SYSTEM_NOTICE' || msg.senderType === 'SYSTEM' ? 'bg-slate-800/50 border border-slate-700 text-slate-400 text-xs italic text-center mx-auto'
          : `bg-[#1c2b3c] border-l-2 border-[#a4c9ff] text-[#d4e4fa] ${isLoadingDots ? 'w-fit' : 'w-full'}`
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
