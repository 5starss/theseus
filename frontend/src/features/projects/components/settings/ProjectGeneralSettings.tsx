import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { projectApi } from '@/features/projects/api';

interface ProjectGeneralSettingsProps {
  projectId: string;
}

export function ProjectGeneralSettings({ projectId }: ProjectGeneralSettingsProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchProjectData = async () => {
      try {
        setIsLoading(true);
        // 참고: 현재는 멤버 권한과 프로젝트 이름만 반환하는 getProjectMe API만 사용 가능합니다.
        // 프로젝트 설명(description)이나 상태(status) 정보가 필요한 경우 별도의 상세 조회 API가 필요할 수 있습니다.
        // 우선은 getProjectMe를 통해 가능한 기본 정보를 가져오고, 상세 정보 API가 준비될 때까지는
        // 임시로 처리하거나 가능한 정보만 사용합니다. 최소한 이름 정보는 getProjectMe에서 가져옵니다.
        const res = await projectApi.getProjectMe(projectId);
        if (cancelled) return;
        setName(res.projectName);
      } catch (err) {
        if (!cancelled) console.error('Failed to load project details', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    fetchProjectData();
    return () => { cancelled = true; };
  }, [projectId]);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await projectApi.updateProject(projectId, {
        name,
        description,
        status: isActive ? 'ACTIVE' : 'INACTIVE',
      });
      alert('프로젝트 정보가 성공적으로 업데이트되었습니다.');
    } catch (err) {
      console.error('Failed to update project', err);
      alert('업데이트에 실패했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center">로딩 중...</div>;
  }

  return (
    <Card className="bg-slate-900/40 backdrop-blur-xl border-slate-800 shadow-2xl shadow-blue-500/5">
      <CardHeader>
        <CardTitle className="text-white font-['Space_Grotesk']">일반 설정</CardTitle>
        <CardDescription className="text-slate-400">프로젝트의 기본 정보를 수정합니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="projectName" className="text-slate-300 font-medium tracking-wide uppercase text-[10px]">프로젝트 이름</Label>
          <Input
            id="projectName"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="프로젝트 이름을 입력하세요"
            className="bg-slate-950/50 border-slate-800 text-slate-200 placeholder:text-slate-600 focus:border-blue-400/50 focus:ring-blue-400/20"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="projectDescription" className="text-slate-300 font-medium tracking-wide uppercase text-[10px]">프로젝트 설명</Label>
          <Textarea
            id="projectDescription"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="프로젝트에 대한 설명을 입력하세요"
            rows={4}
            className="bg-slate-950/50 border-slate-800 text-slate-200 placeholder:text-slate-600 focus:border-blue-400/50 focus:ring-blue-400/20"
          />
        </div>

        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/30 p-4">
          <div className="space-y-0.5">
            <Label className="text-slate-200 font-medium">프로젝트 활성화 상태</Label>
          </div>
          <Switch
            checked={isActive}
            onCheckedChange={setIsActive}
            className="data-[state=checked]:bg-blue-400"
          />
        </div>
      </CardContent>
      <CardFooter className="flex justify-end border-t border-slate-800 p-6">
        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="bg-blue-400 hover:bg-blue-500 text-[#003a6b] font-bold px-8"
        >
          {isSaving ? '저장 중...' : '변경사항 저장'}
        </Button>
      </CardFooter>
    </Card>
  );
}
