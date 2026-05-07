import { apiClient } from '@/api/client';
import type { ApiResponse } from '@/api/auth';
import type { ToolItem, ToolDetailResponse } from '../types';

// 목업 데이터
export const mockTools: ToolItem[] = [
  {
    id: 'tool-1',
    name: 'API 오류 해결사',
    description: '복잡한 엔드포인트 응답을 분석하고 수정 제안을 제공합니다.',
    type: 'BLUE',
    iconName: 'TerminalSquare'
  },
  {
    id: 'tool-2',
    name: '데이터 패턴 분석기',
    description: '대규모 데이터셋에서 숨겨진 상관관계와 이상치를 식별합니다.',
    type: 'AMBER',
    iconName: 'LineChart'
  },
  {
    id: 'tool-3',
    name: '시스템 최적화 도구',
    description: '메모리 누수를 감지하고 리소스 할당을 지능적으로 조정합니다.',
    type: 'BLUE',
    iconName: 'Cpu'
  },
  {
    id: 'tool-4',
    name: '코드 리팩토링 엔진',
    description: '레거시 코드를 현대적인 아키텍처 패턴으로 자동 변환합니다.',
    type: 'BLUE',
    iconName: 'Code'
  },
  {
    id: 'tool-5',
    name: '보안 취약점 스캐너',
    description: '인프라 및 애플리케이션 계층의 잠재적 보안 위험을 스캔합니다.',
    type: 'ROSE',
    iconName: 'ShieldCheck'
  },
  {
    id: 'tool-6',
    name: '성능 메트릭 대시보드',
    description: '실시간 트래픽, 응답 시간 및 서버 상태를 시각화합니다.',
    type: 'BLUE',
    iconName: 'TrendingUp'
  },
  {
    id: 'tool-7',
    name: '로그 집계 엔진',
    description: '여러 서비스의 실시간 로그를 수집하고 비정상 패턴을 탐지합니다.',
    type: 'AMBER',
    iconName: 'FileText'
  },
  {
    id: 'tool-8',
    name: '클라우드 비용 최적화',
    description: '클라우드 인프라 사용량을 분석하여 불필요한 지출을 줄입니다.',
    type: 'BLUE',
    iconName: 'CreditCard'
  },
  {
    id: 'tool-9',
    name: '자동 문서 생성기',
    description: '소스 코드를 분석하여 실시간으로 기술 문서를 업데이트합니다.',
    type: 'BLUE',
    iconName: 'Book'
  },
  {
    id: 'tool-10',
    name: 'API 부하 테스트',
    description: '대규모 동시 접속 상황을 시뮬레이션하여 병목 지점을 찾습니다.',
    type: 'ROSE',
    iconName: 'Zap'
  },
  {
    id: 'tool-11',
    name: 'DB 쿼리 튜너',
    description: '느린 데이터베이스 쿼리를 찾아내고 최적화된 인덱스를 제안합니다.',
    type: 'AMBER',
    iconName: 'Database'
  },
  {
    id: 'tool-12',
    name: '네트워크 토폴로지 맵',
    description: '마이크로서비스 간의 통신 구조를 시각화하고 지연 시간을 추적합니다.',
    type: 'BLUE',
    iconName: 'Share2'
  }
];

export const toolApi = {
  /**
   * 프로젝트 도구 목록 조회
   */
  getTools: async (projectId: string | number): Promise<ToolItem[]> => {
    try {
      const response = await apiClient.get<ApiResponse<ToolItem[]>>(`/api/v1/projects/${projectId}/tools`);
      
      // API 응답이 배열이 아니거나 비어있으면 목업 데이터 반환
      if (!Array.isArray(response.data?.result) || response.data.result.length === 0) {
        console.warn('API returned empty or non-array tools, using mock data.');
        return mockTools;
      }
      
      return response.data.result;
    } catch (error) {
      console.warn('Failed to fetch tools from API, falling back to mock data.', error);
      return mockTools;
    }
  },

  /**
   * 도구 상세 조회
   */
  getTool: async (projectId: string | number, toolId: string | number): Promise<ToolDetailResponse | null> => {
    try {
      const response = await apiClient.get<ApiResponse<ToolDetailResponse>>(`/api/v1/projects/${projectId}/tools/${toolId}`);
      return response.data.result;
    } catch (error) {
      console.warn(`Failed to fetch tool ${toolId} from API, falling back to mock data.`, error);
      
      const longMockCode = `import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ComplexDataAnalyzer:
    """
    A complex data analyzer tool that processes large datasets,
    identifies patterns, and generates comprehensive reports.
    """
    
    def __init__(self, data_source: str):
        self.data_source = data_source
        self.raw_data = []
        self.processed_data = {}
        
    def load_data(self) -> bool:
        logger.info(f"Loading data from {self.data_source}")
        # Simulate data loading
        self.raw_data = [
            {"id": 1, "value": 10.5, "category": "A"},
            {"id": 2, "value": 20.1, "category": "B"},
            {"id": 3, "value": 15.3, "category": "A"},
            {"id": 4, "value": 8.9, "category": "C"},
            {"id": 5, "value": 33.2, "category": "B"},
        ] * 100  # Duplicate to simulate larger dataset
        return True
        
    def clean_data(self) -> None:
        logger.info("Cleaning raw data")
        cleaned = []
        for item in self.raw_data:
            if item.get("value") is not None and item.get("value") > 0:
                cleaned.append(item)
        self.raw_data = cleaned
        
    def analyze_patterns(self) -> Dict[str, float]:
        logger.info("Analyzing data patterns")
        categories = {}
        for item in self.raw_data:
            cat = item["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item["value"])
            
        results = {}
        for cat, values in categories.items():
            results[cat] = sum(values) / len(values)
            
        self.processed_data["averages"] = results
        return results

    def generate_report(self) -> str:
        logger.info("Generating final report")
        report = "Data Analysis Report\\n"
        report += "=" * 20 + "\\n"
        for cat, avg in self.processed_data.get("averages", {}).items():
            report += f"Category {cat}: Average Value = {avg:.2f}\\n"
        return report

def execute(params: Dict[str, Any]) -> str:
    """
    Main entry point for the tool execution.
    """
    source = params.get("source", "default_db")
    
    try:
        analyzer = ComplexDataAnalyzer(source)
        if not analyzer.load_data():
            return "Failed to load data."
            
        analyzer.clean_data()
        analyzer.analyze_patterns()
        
        # Perform some heavy computation simulation
        for i in range(1000):
            _ = i * i
            
        return analyzer.generate_report()
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        return f"Execution failed: {str(e)}"

# Testing block
if __name__ == "__main__":
    print("Running tool locally...")
    result = execute({"source": "local_test_file.csv"})
    print(result)
`;

      // 목업 데이터 반환 (실제 API에러 시 보여줄 임시 데이터)
      return {
        toolId: typeof toolId === 'number' ? toolId : parseInt(toolId.replace(/\D/g, '') || '0', 10),
        fileName: 'complex_data_analyzer.py',
        version: 2,
        pythonCode: longMockCode,
        status: 'APPROVED',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        createdByProjectMemberId: 1
      };
    }
  },
};

