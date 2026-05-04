import { ChatArea } from './ChatArea';
import { InspectorPanel } from './InspectorPanel';

export function ChatDashboard() {
  return (
    <div className="flex h-full w-full bg-[#051424] text-slate-200 overflow-hidden">
      {/* Center: Chat Area */}
      <div className="flex-1 min-w-0 flex flex-col relative h-full">
        <ChatArea />
      </div>

      {/* Right: Inspector / Plan Panel */}
      <div className="w-[380px] flex-shrink-0 bg-[#0b0e14]/60 border-l border-slate-800 flex flex-col relative h-full backdrop-blur-md">
        <InspectorPanel />
      </div>
    </div>
  );
}
