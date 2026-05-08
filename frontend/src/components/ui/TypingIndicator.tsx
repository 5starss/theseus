export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 h-6 px-1 py-1">
      <div className="w-1.5 h-1.5 bg-blue-400/80 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
      <div className="w-1.5 h-1.5 bg-blue-400/80 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
      <div className="w-1.5 h-1.5 bg-blue-400/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
    </div>
  );
}
