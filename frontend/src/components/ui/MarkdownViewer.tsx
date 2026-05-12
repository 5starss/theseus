import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface MarkdownViewerProps {
  content: string;
}

export function MarkdownViewer({ content }: MarkdownViewerProps) {
  // blockId: [id] 형태의 내부 마커를 렌더링 전에 제거합니다.
  const filteredContent = content.replace(/blockId:\s*[\w-]+\s*/gi, '');

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code(props) {
          const { children, className, node: _node, ref: _ref, ...rest } = props;
          void _node;
          void _ref;
          const match = /language-(\w+)/.exec(className || '');
          return match ? (
            <SyntaxHighlighter
              {...rest}
              PreTag="div"
              children={String(children).replace(/\n$/, '')}
              language={match[1]}
              style={vscDarkPlus}
              className="rounded-md border border-slate-700/50 !my-4 !bg-[#1e1e1e]"
            />
          ) : (
            <code {...rest} className={`${className || ''} bg-slate-800/80 rounded px-1.5 py-0.5 text-blue-200 text-[13px] font-mono`}>
              {children}
            </code>
          );
        },
        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed text-[15px] break-words">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-4 space-y-1.5">{children}</ol>,
        li: ({ children }) => <li className="text-slate-300 leading-relaxed">{children}</li>,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline underline-offset-2">{children}</a>,
        h1: ({ children }) => <h1 className="text-2xl font-bold mb-4 mt-6 text-slate-100">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xl font-bold mb-3 mt-5 text-slate-100 border-b border-slate-700/50 pb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-lg font-bold mb-2 mt-4 text-slate-200">{children}</h3>,
        table: ({ children }) => <div className="overflow-x-auto mb-4 border border-slate-700/50 rounded-lg"><table className="w-full text-sm text-left">{children}</table></div>,
        thead: ({ children }) => <thead className="bg-slate-800/50 text-slate-300 uppercase text-xs">{children}</thead>,
        th: ({ children }) => <th className="border-b border-slate-700/50 px-4 py-3 font-semibold">{children}</th>,
        td: ({ children }) => <td className="border-b border-slate-700/50 px-4 py-3 text-slate-300">{children}</td>,
        blockquote: ({ children }) => <blockquote className="border-l-4 border-blue-500/50 pl-4 py-2 my-4 bg-blue-500/5 rounded-r italic text-slate-400">{children}</blockquote>
      }}
    >
      {filteredContent}
    </ReactMarkdown>
  );
}
