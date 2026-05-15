import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolItem } from '../types';

interface ToolCardProps {
  tool: ToolItem;
  onClick?: () => void;
}

export function ToolCard({ tool, onClick }: ToolCardProps) {
  // 통일된 디자인 테마 적용 (BLUE 기반)
  const colors = { gradient: 'from-blue-500/5 to-blue-500/0' };

  return (
    <div
      className="group bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col justify-between h-[160px] relative overflow-hidden transition-all duration-300 hover:border-slate-700 hover:shadow-lg cursor-pointer"
      onClick={onClick}
    >
      {/* 백그라운드 그라데이션 (Hover 시 더 진해짐) */}
      <div
        className={cn(
          "absolute inset-0 bg-gradient-to-br opacity-50 transition-opacity duration-300 group-hover:opacity-100",
          colors.gradient
        )}
      />

      <div className="relative z-10 flex flex-col h-full">
        {/* 상단 타이틀 */}
        <div className="mb-2">
          <h3 className="text-lg font-bold text-slate-200 group-hover:text-white transition-colors line-clamp-1">
            {tool.displayName}
          </h3>
        </div>

        {/* 텍스트 영역 */}
        <div className="flex-1">
          <p className="text-sm text-slate-400 leading-relaxed line-clamp-2">
            {tool.displayDescription}
          </p>
        </div>

        {/* 하단 푸터 (실행하기) */}
        <div className="mt-auto pt-3 flex items-center justify-between">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider group-hover:text-slate-300 transition-colors">
            실행하기
          </span>
          <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors transform group-hover:translate-x-1" />
        </div>
      </div>
    </div>
  );
}
