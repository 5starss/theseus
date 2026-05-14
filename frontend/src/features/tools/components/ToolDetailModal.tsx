import { useState, useEffect } from 'react';
import { X, Code, FileText, CheckCircle, Clock } from 'lucide-react';
import { toolApi } from '../api';
import type { ToolDetailResponse, ToolItem } from '../types';

interface ToolDetailModalProps {
  projectId: string;
  toolItem: ToolItem;
  onClose: () => void;
}

export function ToolDetailModal({ projectId, toolItem, onClose }: ToolDetailModalProps) {
  const [detail, setDetail] = useState<ToolDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchDetail = async () => {
      setIsLoading(true);
      try {
        const data = await toolApi.getTool(projectId, toolItem.toolId);
        if (isMounted) {
          setDetail(data);
        }
      } catch (error) {
        console.error('Failed to fetch tool detail', error);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    fetchDetail();
    return () => { isMounted = false; };
  }, [projectId, toolItem.toolId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#0b0e14] border border-slate-800 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-slate-100">{toolItem.displayName}</h2>
            {detail && (
              <span className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider rounded bg-slate-800 text-slate-400">
                PLAN #{detail.sourceToolPlanId ?? '-'}
              </span>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mb-4" />
              상세 정보를 불러오는 중...
            </div>
          ) : detail ? (
            <div className="space-y-8">
              {/* Meta Info */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <FileText className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">File Name</span>
                  </div>
                  <p className="text-sm text-slate-300 font-mono truncate">{detail.fileName}</p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <CheckCircle className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Status</span>
                  </div>
                  <p className="text-sm text-slate-300">{detail.status}</p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <Clock className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Created At</span>
                  </div>
                  <p className="text-sm text-slate-300 truncate">
                    {new Date(detail.createdAt).toLocaleDateString()}
                  </p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <Clock className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Updated At</span>
                  </div>
                  <p className="text-sm text-slate-300 truncate">
                    {new Date(detail.updatedAt).toLocaleDateString()}
                  </p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <Code className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Module</span>
                  </div>
                  <p className="text-sm text-slate-300 font-mono truncate">{detail.moduleName || '-'}</p>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 mb-1">
                    <FileText className="w-4 h-4" />
                    <span className="text-xs uppercase tracking-wider">Artifact</span>
                  </div>
                  <p className="text-sm text-slate-300 font-mono truncate">{detail.artifactPath || '-'}</p>
                </div>
              </div>

              {/* Code Viewer */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Code className="w-5 h-5 text-blue-400" />
                  <h3 className="text-sm font-medium text-slate-300 uppercase tracking-wider">Python Code</h3>
                </div>
                <div className="bg-[#1e1e1e] rounded-lg border border-slate-800 overflow-hidden">
                  <pre className="p-4 max-h-[50vh] overflow-auto text-sm font-mono text-slate-300 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    <code>{detail.codeSnapshot || detail.metadataJson || '# 생성된 코드 정보를 불러올 수 없습니다.'}</code>
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-20 text-slate-500">
              도구 상세 정보를 찾을 수 없습니다.
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50 flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-4 py-2 rounded text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            닫기
          </button>
          <button 
            className="px-4 py-2 rounded text-sm font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => alert('이 도구를 실행하는 기능은 준비 중입니다.')}
            disabled={detail?.status !== 'APPROVED'}
          >
            이 도구 실행하기
          </button>
        </div>
      </div>
    </div>
  );
}
