import json
import speedtest
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class InternetSpeedToolInput(BaseModel):
    """
    인터넷 속도를 측정하기 위한 입력 모델
    """
    pass

class InternetSpeedTool(BaseTool):
    name = "internet_speed_tool"
    description = "현재 인터넷의 다운로드 속도, 업로드 속도 및 지연 시간(Ping)을 측정합니다."
    input_model = InternetSpeedToolInput
    permission_level = 1

    example_queries = [
        "인터넷 속도 알려줘",
        "인터넷 다운로드 속도 측정해줘",
        "How is my internet speed?",
        "Check network speed"
    ]

    async def execute(self, arguments: InternetSpeedToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            import time
            import socket

            # 1. 매우 가벼운 Ping 측정 (Fallback 준비용)
            start_time = time.time()
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                ping = (time.time() - start_time) * 1000
            except Exception:
                ping = None

            # 2. 본격적인 속도 측정 (speedtest-cli)
            # 만약 speedtest.Speedtest() 호출 시 타임아웃이 발생하면 
            # 이 블록 자체가 except로 넘어갑니다.
            st = speedtest.Speedtest()
            st.get_best_server()
            
            download_speed = st.download() / 1_000_000  # Mbps
            upload_speed = st.upload() / 1_000_000    # Mbps
            if ping is None:
                ping = st.results.ping

            result_data = {
                "download_speed_mbps": round(download_speed, 2),
                "upload_speed_mbps": round(upload_speed, 2),
                "ping_ms": round(ping, 2),
                "unit": "Mbps"
            }

            return ToolResult(output=json.dumps(result_data, ensure_ascii=False, indent=2))

        except Exception as e:
            # 만약 speedtest 라이브러리가 네트워크 문제로 실패할 경우, 
            # 측정된 ping 정보라도 있다면 반환하도록 fallback 시도
            if 'ping' in locals() and ping is not None:
                 return ToolResult(output=json.dumps({
                    "download_speed_mbps": "측정 불가 (타임아웃)",
                    "upload_speed_mbps": "측정 불가 (타임아웃)",
                    "ping_ms": round(ping, 2),
                    "error": str(e)
                }, ensure_ascii=False, indent=2))
            
            return ToolResult(output=f"인터넷 속도 측정 중 오류 발생: {str(e)}", is_error=True)
