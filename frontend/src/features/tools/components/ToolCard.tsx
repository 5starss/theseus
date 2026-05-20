import { ArrowRight, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolItem } from '../types';

interface ToolCardProps {
  tool: ToolItem;
  onClick?: () => void;
  canEditAccessLevel?: boolean;
  isUpdatingAccessLevel?: boolean;
  onAccessLevelChange?: (accessLevel: number) => void;
}

const TOOL_ACCESS_LEVELS = [1, 2, 3, 4, 5];

export function ToolCard({
  tool,
  onClick,
  canEditAccessLevel = false,
  isUpdatingAccessLevel = false,
  onAccessLevelChange,
}: ToolCardProps) {
  // 통일된 디자인 테마 적용 (BLUE 기반)
  const colors = { gradient: 'from-blue-500/5 to-blue-500/0' };
  const accessLevel = tool.toolGrade ?? 1;

  return (
    <div
      className="group bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col justify-between h-[184px] relative overflow-hidden transition-all duration-300 hover:border-slate-700 hover:shadow-lg cursor-pointer"
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
        <div className="mb-2 flex items-start justify-between gap-3">
          <h3 className="min-w-0 text-lg font-bold text-slate-200 group-hover:text-white transition-colors line-clamp-1">
            {tool.displayName}
          </h3>
          <div
            className="shrink-0 flex items-center gap-1.5 rounded border border-blue-500/20 bg-blue-500/10 px-2 py-1 text-xs font-medium text-blue-200"
            title="Tool access level"
            onClick={(event) => event.stopPropagation()}
          >
            <Shield className="h-3.5 w-3.5" />
            {canEditAccessLevel ? (
              <select
                value={accessLevel}
                disabled={isUpdatingAccessLevel}
                onChange={(event) => onAccessLevelChange?.(Number(event.target.value))}
                className="bg-transparent text-blue-100 outline-none disabled:opacity-50"
                aria-label="Tool access level"
              >
                {TOOL_ACCESS_LEVELS.map((level) => (
                  <option key={level} value={level} className="bg-slate-900 text-slate-100">
                    Lv.{level}
                  </option>
                ))}
              </select>
            ) : (
              <span>Lv.{accessLevel}</span>
            )}
          </div>
        </div>

        {/* 텍스트 영역 */}
        <div className="flex-1">
          <p className="text-sm text-slate-400 leading-relaxed line-clamp-2">
            {tool.displayDescription}
          </p>
        </div>

        {/* 하단 푸터 (상세 정보) */}
        <div className="mt-auto pt-3 flex items-center justify-between border-t border-slate-800/30">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider group-hover:text-slate-300 transition-colors">
            상세 정보
          </span>
          <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors transform group-hover:translate-x-1" />
        </div>
      </div>
    </div>
  );
}
