import { useEffect, useState } from 'react';
import { X, Code, FileText, Clock, User, GitBranch } from 'lucide-react';
import { toolApi } from '@/features/tools/api';
import type { ToolDetailResponse } from '@/features/tools/types';
import type { ToolApprovalResponse } from '@/features/projects/types/approval';

interface ToolApprovalDetailModalProps {
  projectId: string;
  approvalItem: ToolApprovalResponse;
  onClose: () => void;
  onActionClick: (type: 'APPROVE' | 'REJECT') => void;
}

export function ToolApprovalDetailModal({
  projectId,
  approvalItem,
  onClose,
  onActionClick
}: ToolApprovalDetailModalProps) {
  const [detail, setDetail] = useState<ToolDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(approvalItem.toolId));

  useEffect(() => {
    let isMounted = true;

    const fetchDetail = async () => {
      if (!approvalItem.toolId) {
        setDetail(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        if (!approvalItem.toolId) return;
        const data = await toolApi.getTool(projectId, approvalItem.toolId);
        if (isMounted) {
          setDetail(data);
        }
      } catch (error) {
        console.error('Failed to fetch tool detail for approval', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    if (approvalItem.toolPlanId) {
      setIsLoading(false);
    } else {
      fetchDetail();
    }
    
    return () => { isMounted = false; };
  }, [projectId, approvalItem.toolId, approvalItem.toolPlanId]);

  const approvalTitle = approvalItem.displayName
    || approvalItem.fileName
    || `ToolPlan #${approvalItem.toolPlanId ?? '-'}`;
  const planStatus = approvalItem.toolPlanStatus || approvalItem.toolStatus || '-';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#0b0e14] border border-slate-800 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-slate-100">{approvalTitle}</h2>
            <span className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
              {approvalItem.draftPhase || planStatus}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mb-4" />
              상세 정보를 불러오는 중...
            </div>
          ) : (
            <div className="space-y-8">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <FileText className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">ToolPlan</span>
                  </div>
                  <p className="text-sm text-slate-300 font-mono truncate">
                    {approvalItem.toolPlanId ?? '-'}
                  </p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <User className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Requested By</span>
                  </div>
                  <p className="text-sm text-slate-300 truncate">{approvalItem.requestedByUserName}</p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <Clock className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Requested At</span>
                  </div>
                  <p className="text-sm text-slate-300 truncate">
                    {new Date(approvalItem.requestedAt).toLocaleDateString()}
                  </p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <GitBranch className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Version</span>
                  </div>
                  <p className="text-sm text-slate-300 truncate">v{approvalItem.planVersion ?? '-'}</p>
                </div>
              </div>

              {/* Code/Artifact Viewer */}
              {approvalItem.toolPlanId ? (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-5 h-5 text-blue-400" />
                    <h3 className="text-sm font-medium text-slate-300 uppercase tracking-wider">Tool Plan Description</h3>
                  </div>
                  <div className="bg-[#1e1e1e] p-6 rounded-lg border border-slate-800 text-center">
                    <p className="text-slate-400 text-sm mb-2">이 승인 요청은 <strong>도구 설계안(Tool Plan)</strong>에 대한 것입니다.</p>
                    <p className="text-slate-500 text-xs">설계안 상세 내용 확인 및 도구 생성 진행은 <br/>요청된 프로젝트의 대화 세션 내에서 확인해 주세요.</p>
                    <div className="mt-4 p-3 bg-slate-900/50 rounded border border-slate-800 font-mono text-[10px] text-slate-500">
                      Artifact Preview: {detail?.codeSnapshot || '실제 Tool 코드는 build 완료 후 생성됩니다.'}
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Code className="w-5 h-5 text-blue-400" />
                    <h3 className="text-sm font-medium text-slate-300 uppercase tracking-wider">Python Code</h3>
                  </div>
                  <div className="bg-[#1e1e1e] rounded-lg border border-slate-800 overflow-hidden">
                    <pre className="p-4 max-h-[50vh] overflow-auto text-sm font-mono text-slate-300 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                      <code>{detail ? (detail.codeSnapshot || '# 파이썬 코드 정보를 불러올 수 없습니다.') : '# 파이썬 코드 정보를 불러올 수 없습니다.'}</code>
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center">
          <div className="text-xs text-slate-500">
            ToolPlan 내용을 확인한 뒤 승인 또는 반려를 진행하세요.
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            >
              닫기
            </button>
            {approvalItem.approvalStatus === 'PENDING' && (
              <>
                <button
                  onClick={() => onActionClick('REJECT')}
                  className="px-4 py-2 rounded text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                >
                  반려
                </button>
                <button
                  onClick={() => onActionClick('APPROVE')}
                  className="px-4 py-2 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-900/20"
                >
                  승인
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
