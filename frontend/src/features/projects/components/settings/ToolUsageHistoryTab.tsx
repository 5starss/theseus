import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Eye } from 'lucide-react';
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
    level: 5,
    toolCreatorName: '김대연',
    toolCreatorEmployeeNo: '1449265',
    usedByName: '손석우',
    usedByEmployeeNo: '1449524',
    status: 'SUCCESS',
    createdAt: '2026-05-29T10:00:00',
    usedAt: '2026-05-29T11:30:00',
    errorMessage: null,
  },
  {
    id: 2,
    toolId: 11,
    toolName: '장애 로그 분석 Tool',
    level: 5,
    toolCreatorName: '김선교',
    toolCreatorEmployeeNo: '1441404',
    usedByName: '일반인',
    usedByEmployeeNo: '1440001',
    status: 'FAILED',
    createdAt: '2026-05-28T14:20:00',
    usedAt: '2026-05-29T09:10:00',
    errorMessage: 'Tool execution failed.',
  },
];

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }

  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const getStatusBadgeClassName = (status: ToolUsageStatus) =>
  cn(
    'font-bold text-[10px] uppercase',
    status === 'SUCCESS'
      ? 'border-green-900 bg-green-950/30 text-green-400'
      : 'border-red-900 bg-red-950/30 text-red-400'
  );

const formatLevel = (level: ToolUsageRow['level']) => {
  if (level === null || level === undefined || level === '') {
    return '-';
  }

  return typeof level === 'number' ? `LV.${level}` : level;
};

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

        // TODO(S14P31A308-483): 백엔드 API 구현 후 mock 플래그를 제거하고 실제 응답을 사용합니다.
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
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 mb-6 min-w-[1100px]">
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
            <Table className="min-w-[1100px]">
              <TableHeader className="bg-slate-950/50">
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="text-slate-400 font-bold uppercase text-[10px] tracking-widest">도구명</TableHead>
                  <TableHead className="w-[90px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">Level</TableHead>
                  <TableHead className="w-[150px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">Tool 생성자</TableHead>
                  <TableHead className="w-[150px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">사용자</TableHead>
                  <TableHead className="w-[120px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">실행 결과</TableHead>
                  <TableHead className="w-[170px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">생성일자</TableHead>
                  <TableHead className="w-[170px] text-slate-400 font-bold uppercase text-[10px] tracking-widest">사용일자</TableHead>
                  <TableHead className="w-[80px] text-center text-slate-400 font-bold uppercase text-[10px] tracking-widest">관리</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow className="border-slate-800">
                    <TableCell colSpan={8} className="text-center py-12 text-slate-500 font-medium">
                      아직 도구 사용 이력이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((row) => (
                    <TableRow key={row.id} className="border-slate-800 hover:bg-slate-900/40 transition-colors">
                      <TableCell>
                        <div className="font-bold text-slate-200">{row.toolName}</div>
                        {row.toolId && <div className="text-xs text-slate-500 font-mono mt-0.5">TOOL #{row.toolId}</div>}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="border-slate-700/50 bg-slate-800/40 text-slate-300 font-bold text-[10px]">
                          {formatLevel(row.level)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-slate-300 font-medium">{row.toolCreatorName}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{row.toolCreatorEmployeeNo}</div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-slate-300 font-medium">{row.usedByName}</div>
                        <div className="text-xs text-slate-500 font-mono mt-0.5">{row.usedByEmployeeNo}</div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={getStatusBadgeClassName(row.status)}>
                          {row.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">{formatDateTime(row.createdAt)}</TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">{formatDateTime(row.usedAt)}</TableCell>
                      <TableCell className="text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-slate-400 hover:text-blue-400 hover:bg-blue-400/10"
                          title="로그 확인"
                        >
                          <Eye className="w-4 h-4" />
                          <span className="sr-only">로그 확인</span>
                        </Button>
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
