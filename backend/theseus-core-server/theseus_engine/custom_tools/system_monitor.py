import json
import psutil
import GPUtil
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class SystemMonitorToolInput(BaseModel):
    """
    시스템 리소스(CPU, RAM, GPU)를 모니터링하기 위한 입력 모델
    """
    pass

class SystemMonitorTool(BaseTool):
    name = "system_monitor"
    description = "현재 시스템의 CPU 사용률, RAM 사용량, GPU VRAM 사용량 및 온도를 조회합니다."
    input_model = SystemMonitorToolInput
    permission_level = 1

    example_queries = [
        "시스템 리소스 확인해줘",
        "CPU랑 GPU 상태 어때?",
        "현재 점유율 보여줘",
        "Check system resource usage"
    ]

    async def execute(self, arguments: SystemMonitorToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            # CPU 사용률 (0.1초 동안의 평균)
            cpu_usage = psutil.cpu_percent(interval=0.1)
            
            # RAM 사용량
            memory = psutil.virtual_memory()
            ram_usage = memory.percent
            ram_used = memory.used / (1024 ** 3)  # GB
            ram_total = memory.total / (1024 ** 3)  # GB

            # GPU 정보
            gpus = GPUtil.getGPUs()
            gpu_info = []
            
            if not gpus:
                gpu_info.append("사용 가능한 GPU를 찾을 수 없습니다.")
            else:
                for gpu in gpus:
                    gpu_info.append({
                        "id": gpu.id,
                        "name": gpu.name,
                        "vram_used": f"{gpu.memoryUsed} MB",
                        "vram_total": f"{gpu.memoryTotal} MB",
                        "vram_percent": f"{gpu.memoryUtil * 100:.1f}%",
                        "temperature": f"{gpu.temperature} °C"
                    })

            result_data = {
                "cpu_usage_percent": f"{cpu_usage}%",
                "ram_usage_percent": f"{ram_usage}%",
                "ram_used_gb": f"{ram_used:.2f} GB",
                "ram_total_gb": f"{ram_total:.2f} GB",
                "gpus": gpu_info
            }

            # [FIX] Convert dict to JSON string to satisfy Pydantic validation (output must be string)
            return ToolResult(output=json.dumps(result_data, ensure_ascii=False, indent=2))

        except Exception as e:
            return ToolResult(output=f"리소스 조회 중 오류 발생: {str(e)}", is_error=True)
