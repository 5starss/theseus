import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { toolUsageApi } from '@/features/projects/api/toolUsage';
import type { ToolUsageRow, ToolUsageStatus } from '@/features/projects/types/toolUsage';

interface ToolUsageHistoryTabProps {
  projectId: string;
}

const USE_MOCK_TOOL_USAGE_DATA = false;

const mockToolUsageRows: ToolUsageRow[] = [
  {
    id: 1,
    toolId: 10,
    toolName: '서버 상태 점검 Tool',
    usedByName: '손석우',
    usedByEmployeeNo: '1449524',
    successCount: 8,
    failedCount: 1,
    status: 'SUCCESS',
    usedAt: '2026-05-29',
  },
  {
    id: 2,
    toolId: 11,
    toolName: '장애 로그 분석 Tool',
    usedByName: '일반인',
    usedByEmployeeNo: '1440001',
    successCount: 2,
    failedCount: 3,
    status: 'FAILED',
    usedAt: '2026-05-29',
  },
];

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }

  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};

const getStatusBadgeClassName = (status?: ToolUsageStatus | null) =>
  cn(
    'font-bold text-[10px] uppercase',
    status === 'SUCCESS'
      ? 'border-green-900 bg-green-950/30 text-green-400'
      : status === 'FAILED'
        ? 'border-red-900 bg-red-950/30 text-red-400'
        : 'border-slate-800 bg-slate-900/50 text-slate-500'
  );

export function ToolUsageHistoryTab({ projectId }: ToolUsageHistoryTabProps) {
  const [rows, setRows] = useState<ToolUsageRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchToolUsages = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        if (USE_MOCK_TOOL_USAGE_DATA) {
          setRows(mockToolUsageRows);
          return;
        }

        const response = await toolUsageApi.getToolUsages(projectId);
        if (!cancelled) {
          setRows(response.items || []);
        }
      } catch (error) {
        console.error('Failed to fetch tool usage history:', error);
        if (!cancelled) {
          setErrorMessage(null);
          setRows(mockToolUsageRows);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchToolUsages();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <Card className="bg-slate-900/40 backdrop-blur-xl border-slate-800 shadow-2xl shadow-blue-500/5 overflow-x-auto">
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 mb-6 min-w-[900px]">
        <div className="min-w-max">
          <CardTitle className="text-white font-['Space_Grotesk'] mb-1 whitespace-nowrap">도구 사용 목록</CardTitle>
          <CardDescription className="text-slate-400 whitespace-nowrap">
            프로젝트 내 도구 호출 이력과 실행 결과를 관리합니다.
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="py-12 text-center text-slate-500 animate-pulse">도구 사용 이력을 불러오는 중입니다.</div>
        ) : errorMessage ? (
          <div className="py-12 text-center text-red-400 font-medium">{errorMessage}</div>
        ) : (
          <div className="border border-slate-800 rounded-lg overflow-x-auto bg-slate-950/20">
            <Table className="min-w-[900px]">
              <TableHeader className="bg-slate-950/50">
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="w-[180px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">사용자</TableHead>
                  <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">도구명</TableHead>
                  <TableHead className="w-[120px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">성공 횟수</TableHead>
                  <TableHead className="w-[120px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">실패 횟수</TableHead>
                  <TableHead className="w-[170px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">사용일자</TableHead>
                  <TableHead className="w-[120px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">실행 결과</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow className="border-slate-800">
                    <TableCell colSpan={6} className="text-center py-12 text-slate-500 font-medium">
                      프로젝트 멤버가 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((row) => (
                    <TableRow key={row.id} className="border-slate-800 hover:bg-slate-900/40 transition-colors">
                      <TableCell>
                        <div className="text-sm text-slate-300 font-medium">{row.usedByName}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{row.usedByEmployeeNo}</div>
                      </TableCell>
                      <TableCell>
                        <div className="font-bold text-slate-200">{row.toolName || '-'}</div>
                        {row.toolId && <div className="text-xs text-slate-500 font-mono mt-0.5">TOOL #{row.toolId}</div>}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="border-green-900 bg-green-950/30 text-green-400 font-bold text-[10px]">
                          {row.successCount}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="border-red-900 bg-red-950/30 text-red-400 font-bold text-[10px]">
                          {row.failedCount}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">{formatDateTime(row.usedAt)}</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={getStatusBadgeClassName(row.status)}>
                          {row.status || '-'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
