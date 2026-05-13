import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CheckCircle2, XCircle, Clock, Eye } from 'lucide-react';
import { approvalApi } from '@/features/projects/api/approval';
import type { ToolApprovalResponse } from '@/features/projects/types/approval';
import { ToolApprovalDetailModal } from './ToolApprovalDetailModal';

const DEFAULT_TOOL_GRADE = 1;
const MAX_PUBLIC_TOOL_GRADE = 99;

const clampPublicToolGrade = (value: number) =>
  Math.min(MAX_PUBLIC_TOOL_GRADE, Math.max(DEFAULT_TOOL_GRADE, value));

interface ToolApprovalManagementProps {
  projectId: string;
}

export function ToolApprovalManagement({ projectId }: ToolApprovalManagementProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filterStatus = searchParams.get('status') || 'PENDING';

  const setFilterStatus = (status: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('status', status);
      return next;
    }, { replace: true });
  };

  const [approvals, setApprovals] = useState<ToolApprovalResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  // States for Detail Modal
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedDetailApproval, setSelectedDetailApproval] = useState<ToolApprovalResponse | null>(null);

  // States for Approve/Reject Dialog
  const [isActionOpen, setIsActionOpen] = useState(false);
  const [selectedApproval, setSelectedApproval] = useState<ToolApprovalResponse | null>(null);
  const [actionType, setActionType] = useState<'APPROVE' | 'REJECT'>('APPROVE');

  // Form states
  const [toolGrade, setToolGrade] = useState<number>(DEFAULT_TOOL_GRADE);
  const [reviewFeedback, setReviewFeedback] = useState('');

  const refetch = () => setFetchTrigger(n => n + 1);

  useEffect(() => {
    let cancelled = false;
    const fetchApprovals = async () => {
      setIsLoading(true);
      try {
        const statusParam = filterStatus === 'ALL' ? undefined : filterStatus;
        const res = await approvalApi.getToolApprovals(projectId, 0, 50, statusParam);
        if (cancelled) return;
        setApprovals(res.content || []);
      } catch (err) {
        if (!cancelled) console.error('Failed to fetch tool approvals', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchApprovals();
    return () => { cancelled = true; };
  }, [projectId, fetchTrigger, filterStatus]);

  const openDetailModal = (approval: ToolApprovalResponse) => {
    setSelectedDetailApproval(approval);
    setIsDetailOpen(true);
  };

  const openActionModal = (approval: ToolApprovalResponse, type: 'APPROVE' | 'REJECT') => {
    setSelectedApproval(approval);
    setActionType(type);
    setToolGrade(DEFAULT_TOOL_GRADE);
    setReviewFeedback('');
    setIsActionOpen(true);
  };

  const handleDetailActionClick = (type: 'APPROVE' | 'REJECT') => {
    if (selectedDetailApproval) {
      setIsDetailOpen(false);
      openActionModal(selectedDetailApproval, type);
    }
  };

  const handleActionSubmit = async () => {
    if (!selectedApproval) return;

    try {
      if (actionType === 'APPROVE') {
        await approvalApi.approveTool(projectId, selectedApproval.toolApprovalId, {
          toolGrade,
          reviewFeedback
        });
        toast.success('도구가 승인되었습니다.');
      } else {
        if (!reviewFeedback.trim()) {
          toast.warning('반려 사유를 입력해주세요.');
          return;
        }
        await approvalApi.rejectTool(projectId, selectedApproval.toolApprovalId, {
          reviewFeedback
        });
        toast.success('도구가 반려되었습니다.');
      }
      setIsActionOpen(false);
      refetch();
    } catch (err) {
      console.error('Action failed', err);
      toast.error('처리에 실패했습니다.');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'PENDING': return <Clock className="w-3 h-3 text-amber-500" />;
      case 'APPROVED': return <CheckCircle2 className="w-3 h-3 text-green-500" />;
      case 'REJECTED': return <XCircle className="w-3 h-3 text-red-500" />;
      default: return null;
    }
  };

  return (
    <>
      <Card className="bg-slate-900/40 backdrop-blur-xl border-slate-800 shadow-2xl shadow-blue-500/5 overflow-x-auto">
        <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 mb-6 min-w-[900px]">
          <div className="min-w-max">
            <CardTitle className="text-white font-['Space_Grotesk'] mb-1 whitespace-nowrap">도구 승인 대기열</CardTitle>
            <CardDescription className="text-slate-400 whitespace-nowrap">멤버들이 생성 요청한 도구를 검토하고 승인합니다.</CardDescription>
          </div>

          <div className="flex items-center gap-3">
            <Label className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">필터</Label>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[140px] bg-slate-950/50 border-slate-800 text-slate-200">
                <SelectValue placeholder="상태 필터" />
              </SelectTrigger>
              <SelectContent className="bg-slate-900 border-slate-800 text-white">
                <SelectItem value="ALL">전체 보기</SelectItem>
                <SelectItem value="PENDING">대기 중</SelectItem>
                <SelectItem value="APPROVED">승인됨</SelectItem>
                <SelectItem value="REJECTED">반려됨</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="py-12 text-center text-slate-500 animate-pulse">요청 목록을 불러오는 중...</div>
          ) : (
            <div className="border border-slate-800 rounded-lg overflow-x-auto bg-slate-950/20">
              <Table className="min-w-[900px]">
                <TableHeader className="bg-slate-950/50">
                  <TableRow className="border-slate-800 hover:bg-transparent">
                    <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">도구 이름 / 유형</TableHead>
                    <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">요청자</TableHead>
                    <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">상태</TableHead>
                    <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">요청일</TableHead>
                    <TableHead className="text-right text-slate-400 font-bold uppercase text-[10px] tracking-widest">작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {approvals.length === 0 ? (
                    <TableRow className="border-slate-800">
                      <TableCell colSpan={5} className="text-center py-12 text-slate-500 font-medium">
                        대기 중인 승인 요청이 없습니다.
                      </TableCell>
                    </TableRow>
                  ) : (
                    approvals.map(approval => (
                      <TableRow key={approval.toolApprovalId} className="border-slate-800 hover:bg-slate-900/40 transition-colors">
                        <TableCell>
                          <div className="font-bold text-slate-200">
                            {approval.displayName || approval.fileName || `설계안 #${approval.toolPlanId ?? '-'}`}
                            {approval.toolPlanId && <span className="ml-2 text-[10px] text-blue-400 font-normal border border-blue-400/30 px-1 py-0.5 rounded">설계안</span>}
                          </div>
                          <div className="text-[10px] text-blue-400 font-mono mt-0.5 tracking-wider uppercase">
                            {approval.toolPlanStatus || approval.toolStatus || '-'}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm text-slate-300 font-medium">{approval.requestedByUserName}</div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(approval.approvalStatus)}
                            <Badge variant="outline" className={cn(
                              "font-bold text-[10px] uppercase",
                              approval.approvalStatus === 'PENDING' ? "border-amber-900 bg-amber-950/30 text-amber-400" :
                                approval.approvalStatus === 'APPROVED' ? "border-green-900 bg-green-950/30 text-green-400" :
                                  "border-red-900 bg-red-950/30 text-red-400"
                            )}>
                              {approval.approvalStatus}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-slate-500 font-mono">
                          {new Date(approval.requestedAt).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-slate-800 bg-slate-900/40 text-slate-400 hover:bg-slate-800 hover:text-slate-100 font-bold text-[11px] transition-all"
                              onClick={() => openDetailModal(approval)}
                            >
                              <Eye className="w-3 h-3 mr-1.5" />
                              상세 보기
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>

        <Dialog open={isActionOpen} onOpenChange={setIsActionOpen}>
          <DialogContent className="max-w-lg bg-[#0b1424] border-slate-800 text-slate-100">
            <DialogHeader>
              <DialogTitle className="text-white flex items-center gap-2">
                <Clock className="w-5 h-5 text-blue-400" /> 도구 승인 검토
              </DialogTitle>
              <DialogDescription className="text-slate-400 font-medium">
                <span className="text-blue-400 font-bold">{selectedApproval?.displayName || selectedApproval?.fileName || '도구/설계안'}</span>에 대한 승인 요청을 검토합니다.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6 py-6">
              <div className="space-y-4">
                <Label className="text-slate-300 uppercase text-[10px] font-bold tracking-widest">승인 결정</Label>
                <div className="flex gap-4">
                  <Button
                    variant={actionType === 'APPROVE' ? 'default' : 'outline'}
                    onClick={() => setActionType('APPROVE')}
                    className={cn(
                      "flex-1 font-bold",
                      actionType === 'APPROVE' ? "bg-green-600 hover:bg-green-700 text-white" : "border-slate-800 text-slate-500 hover:bg-slate-900"
                    )}
                  >
                    승인 (Approve)
                  </Button>
                  <Button
                    variant={actionType === 'REJECT' ? 'default' : 'outline'}
                    onClick={() => setActionType('REJECT')}
                    className={cn(
                      "flex-1 font-bold",
                      actionType === 'REJECT' ? "bg-red-600 hover:bg-red-700 text-white" : "border-slate-800 text-slate-500 hover:bg-slate-900"
                    )}
                  >
                    반려 (Reject)
                  </Button>
                </div>
              </div>

              {actionType === 'APPROVE' && !selectedApproval?.toolPlanId && (
                <div className="space-y-2">
                  <Label className="text-slate-300 uppercase text-[10px] font-bold tracking-widest">도구 등급 (Tool Grade)</Label>
                  <Input
                    type="number"
                    min={DEFAULT_TOOL_GRADE}
                    max={MAX_PUBLIC_TOOL_GRADE}
                    value={toolGrade}
                    onChange={(e) => setToolGrade(clampPublicToolGrade(Number(e.target.value)))}
                    className="bg-slate-950 border-slate-800 text-white"
                  />
                  <p className="text-[11px] text-slate-500">Public range: 1-99</p>
                </div>
              )}

              <div className="space-y-2">
                <Label className="text-slate-300 uppercase text-[10px] font-bold tracking-widest">검토 의견</Label>
                <Textarea
                  placeholder={actionType === 'APPROVE' ? "승인 사유를 입력하세요..." : "반려 사유를 입력하세요..."}
                  value={reviewFeedback}
                  onChange={(e) => setReviewFeedback(e.target.value)}
                  className="bg-slate-950 border-slate-800 text-white min-h-[100px]"
                />
              </div>
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setIsActionOpen(false)} className="border-slate-700 text-slate-300 hover:bg-slate-800">취소</Button>
              <Button
                onClick={handleActionSubmit}
                className={cn(
                  "font-bold px-8",
                  actionType === 'APPROVE' ? "bg-green-600 hover:bg-green-700 text-white" : "bg-red-600 hover:bg-red-700 text-white"
                )}
              >
                {actionType === 'APPROVE' ? '승인하기' : '반려하기'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Card>

      {isDetailOpen && selectedDetailApproval && (
        <ToolApprovalDetailModal
          projectId={projectId}
          approvalItem={selectedDetailApproval}
          onClose={() => setIsDetailOpen(false)}
          onActionClick={handleDetailActionClick}
        />
      )}
    </>
  );
}
