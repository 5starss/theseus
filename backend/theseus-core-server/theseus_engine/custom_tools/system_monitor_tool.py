import json
import psutil
from typing import Any, Dict, Optional
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class SystemMonitorToolInput(BaseModel):
    """
    시스템 모니터링을 위한 입력 모델. 
    현재는 모든 정보를 기본으로 수집하며, 필요 시 필터를 추가할 수 있습니다.
    """
    pass

class SystemMonitorTool(BaseTool):
    """
    현재 시스템의 CPU, RAM, 그리고 NVIDIA GPU(VRAM, 온도 등)의 리소스 상태를 조회하는 도구입니다.
    
    의존성:
    - psutil
    - nvidia-ml-py (pynvml)
    
    설치 방법:
    pip install psutil nvidia-ml-py
    """
    name = "system_monitor_tool"
    description = "현재 시스템의 CPU, RAM 사용량 및 GPU(VRAM, 온도 등) 상태를 실시간으로 조회합니다."
    input_model = SystemMonitorToolInput
    permission_level = 1

    example_queries = [
        "시스템 상태 알려줘",
        "CPU랑 RAM 점유율 얼마야?",
        "GPU 온도랑 VRAM 사용량 확인해줘",
        "Check system resource usage",
        "Show me CPU and GPU status"
    ]

    async def execute(self, arguments: SystemMonitorToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            result_data: Dict[str, Any] = {
                "cpu": {},
                "memory": {},
                "gpu": []
            }

            # 1. CPU 정보 수집
            result_data["cpu"] = {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False)
            }

            # 2. RAM 정보 수집
            mem = psutil.virtual_memory()
            result_data["memory"] = {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "usage_percent": mem.percent
            }

            # 3. GPU 정보 수집 (NVIDIA 전용)
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()

                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    # name 추출 시 버전에 따라 에러가 날 수 있어 try-except 처리
                    try:
                        name = pynvml.nvmlDeviceGetName(handle)
                    except:
                        name = f"NVIDIA GPU {i}"
                    
                    # 메모리 정보
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    # 온도 정보
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    # 사용률 정보
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                    gpu_info = {
                        "index": i,
                        "name": name,
                        "vram_total_gb": round(mem_info.total / (1024**3), 2),
                        "vram_used_gb": round(mem_info.used / (1024**3), 2),
                        "vram_free_gb": round(mem_info.free / (1024**3), 2),
                        "vram_usage_percent": round((mem_info.used / mem_info.total) * 100, 2),
                        "gpu_usage_percent": util.gpu,
                        "memory_usage_percent": util.memory,
                        "temperature_c": temp
                    }
                    result_data["gpu"].append(gpu_info)

                pynvml.nvmlShutdown()
            except Exception as gpu_err:
                # GPU가 없거나 드라이버 문제인 경우 에러 메시지를 포함하되 전체 툴이 실패하지 않도록 처리
                result_data["gpu"] = f"GPU 정보 조회 불가: {str(gpu_err)}"

            return ToolResult(output=json.dumps(result_data, ensure_ascii=False, indent=2))

        except Exception as e:
            return ToolResult(output=f"시스템 모니터링 중 오류 발생: {str(e)}", is_error=True)
