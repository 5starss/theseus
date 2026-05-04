import { useChatSessionStore } from '../../stores/useChatSessionStore';

export function ChatArea() {
  const messages = useChatSessionStore(state => state.messages);

  return (
    <div className="flex flex-col h-full relative">
      {/* Background Grid Effect */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-20 pointer-events-none" />
      
      {/* Top App Bar (Workspace Info) */}
      <div className="h-14 border-b border-slate-800 bg-[#0b0e14]/60 backdrop-blur flex items-center px-6 z-20">
        <span className="text-xs font-bold text-slate-500">WORKSPACE</span>
        <span className="mx-2 text-slate-600">/</span>
        <span className="text-xs font-medium text-blue-400">새 세션</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-8 space-y-6 z-10">
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.sender === 'USER' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] p-4 rounded-lg ${msg.sender === 'USER' ? 'bg-[#3e495d] text-[#aeb9d0]' : 'bg-[#1c2b3c] border-l-2 border-[#a4c9ff] text-[#d4e4fa]'}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {messages.length === 0 && (
          <div className="text-slate-500 flex justify-center items-center h-full">
            새로운 지시를 내려 AI와 대화를 시작하세요.
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="px-8 pb-8 pt-4 bg-gradient-to-t from-[#051424] via-[#051424]/90 to-transparent z-10">
        <div className="bg-[#0d1c2d] border border-slate-700/50 rounded-lg p-3 flex items-end shadow-lg shadow-blue-500/5">
          <textarea
            className="flex-1 bg-transparent border-none outline-none resize-none px-3 py-2 text-sm text-slate-300 placeholder-slate-500 min-h-[40px] max-h-[200px]"
            rows={1}
            placeholder="AI에게 다음 작업을 지시하세요..."
          />
          <button className="bg-blue-400 hover:bg-blue-500 text-slate-900 px-6 py-2 rounded text-xs font-bold transition-colors ml-4 uppercase tracking-wider">
            보내기
          </button>
        </div>
        <div className="text-center mt-4 text-[10px] text-slate-500 tracking-wider font-mono">
          POWERED BY THESEUS GEN-2 ENGINE • HIGH PRECISION MODE ACTIVE
        </div>
      </div>
    </div>
  );
}
