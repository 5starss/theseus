import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Folder } from 'lucide-react';
import { projectApi } from '@/features/projects/api';
import type { MyProjectResponse } from '@/features/projects/api';

export default function ProjectListPage() {
  const [projects, setProjects] = useState<MyProjectResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setIsLoading(true);
        // Temporarily fetching page 0, size 20
        const data = await projectApi.getMyProjects(0, 20);
        setProjects(data.content);
      } catch (error) {
        console.error('Failed to fetch projects', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjects();
  }, []);

  return (
    <div className="content-stretch flex flex-col items-center pb-[100px] pt-[64px] px-[24px] relative size-full min-h-screen">
      {/* Background Decorative Elements */}
      <div className="absolute bg-[rgba(164,201,255,0.05)] blur-[60px] bottom-[-49px] h-[512px] right-0 rounded-[12px] w-[426.66px] pointer-events-none" />
      <div className="absolute bg-[rgba(250,189,52,0.05)] blur-[50px] h-[341.33px] left-0 rounded-[12px] top-[80px] w-[320px] pointer-events-none" />

      <div className="content-stretch flex flex-col items-start max-w-[896px] pb-[32px] relative shrink-0 w-full z-10">
        <div className="content-stretch flex flex-col gap-[8px] items-center max-w-[896px] relative shrink-0 w-full">
          <div className="content-stretch flex flex-col items-center relative shrink-0 w-full">
            <h1 className="font-medium text-[#d4e4fa] text-[24px] tracking-[-0.4px]">
              프로젝트
            </h1>
          </div>
          <div className="content-stretch flex flex-col items-center opacity-70 relative shrink-0 w-full">
            <p className="font-medium text-[#c1c7d3] text-[16px] text-center">
              현재 참여 중인 연구 및 시스템 자동화 프로젝트 목록입니다.
            </p>
          </div>
        </div>
      </div>

      <div className="content-stretch flex flex-col gap-[16px] items-start max-w-[896px] relative shrink-0 w-full z-10">
        {isLoading ? (
          <div className="w-full flex justify-center py-20 text-[#8b919d]">
            프로젝트 정보를 불러오는 중입니다...
          </div>
        ) : projects.length === 0 ? (
          <div className="w-full flex justify-center py-20 text-[#8b919d]">
            참여 중인 프로젝트가 없습니다.
          </div>
        ) : (
          projects.map((project) => (
            <div
              key={project.projectId}
              onClick={() => navigate(`/projects/${project.projectId}`)}
              className="backdrop-blur-[6px] bg-[rgba(30,41,59,0.4)] border border-[rgba(65,71,81,0.3)] hover:border-[rgba(96,165,250,0.5)] hover:bg-[rgba(30,41,59,0.6)] transition-all cursor-pointer content-stretch flex items-center justify-between p-[25px] relative rounded-[8px] shrink-0 w-full group"
            >
              <div className="relative shrink-0 flex-1">
                <div className="flex gap-[24px] items-center relative size-full">
                  <div className="border border-[rgba(65,71,81,0.2)] bg-[#273647] flex items-center justify-center p-px relative rounded-[4px] shrink-0 size-[64px] shadow-[inset_0px_2px_4px_0px_rgba(0,0,0,0.05)] group-hover:bg-[#2d3f54] transition-colors">
                    <Folder className="w-8 h-8 text-[#60a5fa]" />
                  </div>
                  <div className="flex flex-col gap-[8px] items-start relative flex-1 min-w-0">
                    <div className="flex gap-[12px] items-center relative w-full">
                      <div className="flex flex-col items-start relative shrink-0">
                        <h3 className="font-medium text-[#d4e4fa] text-[18px] truncate">
                          {project.name}
                        </h3>
                      </div>
                      <div className="flex gap-[8px] items-center relative shrink-0">
                        <div className={`border content-stretch flex flex-col items-start px-[9px] py-[3px] relative rounded-[2px] shrink-0 ${project.projectStatus === 'ACTIVE' ? 'bg-[rgba(164,201,255,0.1)] border-[rgba(164,201,255,0.2)]' : 'bg-[rgba(156,163,175,0.1)] border-[rgba(156,163,175,0.2)]'}`}>
                          <span className={`font-normal text-[10px] leading-[15px] ${project.projectStatus === 'ACTIVE' ? 'text-[#a4c9ff]' : 'text-gray-400'}`}>
                            {project.projectStatus}
                          </span>
                        </div>
                        <div className={`border content-stretch flex flex-col items-start px-[9px] py-[3px] relative rounded-[2px] shrink-0 ${project.projectRole === 'ADMIN' ? 'bg-[rgba(250,189,52,0.1)] border-[rgba(250,189,52,0.2)]' : 'bg-[rgba(52,211,153,0.1)] border-[rgba(52,211,153,0.2)]'}`}>
                          <span className={`font-normal text-[10px] leading-[15px] ${project.projectRole === 'ADMIN' ? 'text-[#fabd34]' : 'text-[#34d399]'}`}>
                            {project.projectRole}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col items-start w-full pr-4">
                      <p className="font-medium text-[#c1c7d3] text-[14px] leading-[22px] line-clamp-2">
                        {project.description}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="relative shrink-0 flex flex-col items-end gap-[3px]">
                <span className="font-medium text-[#8b919d] text-[12px] leading-[15px]">최근 업데이트</span>
                <span className="font-mono text-[#c1c7d3] text-[13px] leading-[16.5px]">
                  {new Date(project.updatedAt).toLocaleString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                  }).replace(/\. /g, '.').replace(':', ':')}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
