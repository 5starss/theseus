import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Server, Trash2, Wifi } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { remoteWorkspaceApi } from '../../api/remoteWorkspace';
import type { RemoteWorkspaceResponse } from '../../types/project';

interface RemoteWorkspaceManagementProps {
  projectId: string;
}

const EMPTY_FORM = {
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  privateKeyPath: '',
  basePath: '/',
};

export function RemoteWorkspaceManagement({ projectId }: RemoteWorkspaceManagementProps) {
  const [remoteWorkspaces, setRemoteWorkspaces] = useState<RemoteWorkspaceResponse[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);

  const loadRemoteWorkspaces = async () => {
    try {
      setIsLoading(true);
      const responses = await remoteWorkspaceApi.getRemoteWorkspaces(projectId);
      setRemoteWorkspaces(responses);
    } catch (error) {
      console.error('Failed to load remote workspaces', error);
      toast.error('Remote Workspace 목록을 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadRemoteWorkspaces();
  }, [projectId]);

  const handleCreate = async () => {
    if (!form.name.trim() || !form.host.trim() || !form.username.trim() || !form.basePath.trim()) {
      toast.warning('이름, host, username, basePath를 입력해주세요.');
      return;
    }

    try {
      setIsSaving(true);
      await remoteWorkspaceApi.createRemoteWorkspace(projectId, {
        name: form.name.trim(),
        host: form.host.trim(),
        port: Number(form.port),
        username: form.username.trim(),
        password: form.password || undefined,
        privateKeyPath: form.privateKeyPath || undefined,
        basePath: form.basePath.trim(),
      });
      setForm(EMPTY_FORM);
      toast.success('Remote Workspace를 등록했습니다.');
      await loadRemoteWorkspaces();
    } catch (error) {
      console.error('Failed to create remote workspace', error);
      toast.error('Remote Workspace 등록에 실패했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async (remoteWorkspaceId: number) => {
    try {
      setTestingId(remoteWorkspaceId);
      const result = await remoteWorkspaceApi.testConnection(projectId, remoteWorkspaceId);
      if (result.available) {
        toast.success(result.message || 'Remote Workspace 연결에 성공했습니다.');
      } else {
        toast.error(result.message || 'Remote Workspace 연결에 실패했습니다.');
      }
    } catch (error) {
      console.error('Failed to test remote workspace', error);
      toast.error('Remote Workspace 연결 테스트에 실패했습니다.');
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (remoteWorkspaceId: number) => {
    try {
      await remoteWorkspaceApi.deleteRemoteWorkspace(projectId, remoteWorkspaceId);
      toast.success('Remote Workspace를 삭제했습니다.');
      await loadRemoteWorkspaces();
    } catch (error) {
      console.error('Failed to delete remote workspace', error);
      toast.error('Remote Workspace 삭제에 실패했습니다.');
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card className="bg-slate-900/40 border-slate-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Server className="h-4 w-4 text-blue-400" />
            Remote Workspace
          </CardTitle>
          <CardDescription className="text-slate-400">
            프로젝트에서 사용할 외부 서버 실행 환경을 등록합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="rounded border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
              Remote Workspace를 불러오는 중입니다.
            </div>
          ) : remoteWorkspaces.length === 0 ? (
            <div className="rounded border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
              등록된 Remote Workspace가 없습니다.
            </div>
          ) : (
            remoteWorkspaces.map(workspace => (
              <div
                key={workspace.remoteWorkspaceId}
                className="flex flex-col gap-3 rounded border border-slate-800 bg-slate-950/40 p-4 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <div className="font-semibold text-slate-100">{workspace.name}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {workspace.username}@{workspace.host}:{workspace.port} · {workspace.basePath}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800"
                    disabled={testingId === workspace.remoteWorkspaceId}
                    onClick={() => handleTestConnection(workspace.remoteWorkspaceId)}
                  >
                    <Wifi className="mr-2 h-4 w-4" />
                    {testingId === workspace.remoteWorkspaceId ? '확인 중' : '연결 테스트'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="border-red-900/60 bg-slate-900 text-red-300 hover:bg-red-950/30"
                    onClick={() => handleDelete(workspace.remoteWorkspaceId)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="bg-slate-900/40 border-slate-800">
        <CardHeader>
          <CardTitle className="text-white">등록</CardTitle>
          <CardDescription className="text-slate-400">
            알파 단계에서는 비밀번호 또는 private key path 중 하나를 사용합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-slate-300">이름</Label>
            <Input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              className="bg-slate-950/50 border-slate-800 text-slate-200"
            />
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)_88px] gap-2">
            <div className="space-y-2">
              <Label className="text-slate-300">Host</Label>
              <Input
                value={form.host}
                onChange={(event) => setForm({ ...form, host: event.target.value })}
                className="bg-slate-950/50 border-slate-800 text-slate-200"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">Port</Label>
              <Input
                type="number"
                min={1}
                max={65535}
                value={form.port}
                onChange={(event) => setForm({ ...form, port: Number(event.target.value) })}
                className="bg-slate-950/50 border-slate-800 text-slate-200"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-slate-300">Username</Label>
            <Input
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              className="bg-slate-950/50 border-slate-800 text-slate-200"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-slate-300">Password</Label>
            <Input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              className="bg-slate-950/50 border-slate-800 text-slate-200"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-slate-300">Private Key Path</Label>
            <Input
              value={form.privateKeyPath}
              onChange={(event) => setForm({ ...form, privateKeyPath: event.target.value })}
              className="bg-slate-950/50 border-slate-800 text-slate-200"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-slate-300">Base Path</Label>
            <Input
              value={form.basePath}
              onChange={(event) => setForm({ ...form, basePath: event.target.value })}
              className="bg-slate-950/50 border-slate-800 text-slate-200"
            />
          </div>
          <Button
            type="button"
            disabled={isSaving}
            onClick={handleCreate}
            className="w-full bg-blue-400 text-[#003a6b] hover:bg-blue-500"
          >
            {isSaving ? '등록 중' : 'Remote Workspace 등록'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
