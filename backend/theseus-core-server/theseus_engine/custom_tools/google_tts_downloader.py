
import os
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

# google-cloud-texttospeech 라이브러리가 필요합니다.
# 설치: pip install google-cloud-texttospeech
# 인증: gcloud auth application-default login
try:
    from google.cloud import texttospeech
    from google.api_core import exceptions as google_exceptions
except ImportError:
    # 이 예외는 도구가 로드될 때가 아니라, 사용자가 라이브러리 없이 실행을 시도할 때 발생합니다.
    # 따라서 이 임포트 에러는 execute 메서드 내에서 처리하는 것이 더 적합하지만,
    # 코드 상단에 명시하여 의존성을 명확히 합니다.
    texttospeech = None
    google_exceptions = None

class GoogleTTSDownloaderInput(BaseModel):
    """Google Cloud Text-to-Speech를 사용하여 텍스트를 음성 파일로 변환하기 위한 입력 모델입니다."""
    text_to_synthesize: str = Field(..., description="음성으로 변환할 텍스트입니다.")
    output_file_path: str = Field(..., description="생성된 MP3 음성 파일을 저장할 경로입니다. 예: 'output.mp3'")
    language_code: str = Field(default="ko-KR", description="음성의 언어 코드입니다. 예: 'en-US', 'ko-KR'")
    voice_name: str = Field(default="ko-KR-Standard-A", description="음성의 이름입니다. 예: 'en-US-Wavenet-F', 'ko-KR-Standard-A'")

class GoogleTTSDownloaderTool(BaseTool):
    """
    Google Cloud Text-to-Speech API를 사용하여 텍스트를 음성 파일로 변환하고 저장하는 도구입니다.

    **사전 요구사항:**
    1. `google-cloud-texttospeech` 라이브러리를 설치해야 합니다:
       `pip install google-cloud-texttospeech`
    2. Google Cloud SDK를 설치하고 애플리케이션 기본 사용자 인증 정보를 설정해야 합니다:
       `gcloud auth application-default login`
    """
    name = "google_tts_downloader"
    description = "Google Cloud TTS API를 사용하여 텍스트를 음성 파일로 변환합니다."
    input_model = GoogleTTSDownloaderInput
    permission_level = 1

    async def execute(
        self, arguments: GoogleTTSDownloaderInput, context: ToolExecutionContext
    ) -> ToolResult:
        """주어진 텍스트를 Google TTS API를 통해 음성 파일로 합성하고 저장합니다."""
        if not texttospeech or not google_exceptions:
            return ToolResult(
                output="필수 라이브러리가 설치되지 않았습니다. 'pip install google-cloud-texttospeech'를 실행해주세요.",
                is_error=True,
            )

        try:
            # 클라이언트 초기화
            client = texttospeech.TextToSpeechClient()

            # 입력 텍스트 설정
            synthesis_input = texttospeech.SynthesisInput(text=arguments.text_to_synthesize)

            # 음성 파라미터 설정
            voice = texttospeech.VoiceSelectionParams(
                language_code=arguments.language_code, name=arguments.voice_name
            )

            # 오디오 형식 설정
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            # API 요청
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # 출력 디렉토리 확인 및 생성
            output_dir = os.path.dirname(arguments.output_file_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # MP3 파일로 저장
            with open(arguments.output_file_path, "wb") as out:
                out.write(response.audio_content)

            return ToolResult(
                output=f"음성 파일이 성공적으로 생성되어 '{arguments.output_file_path}'에 저장되었습니다."
            )

        except google_exceptions.PermissionDenied:
            return ToolResult(
                output="Google Cloud 인증에 실패했습니다. 'gcloud auth application-default login'을 실행하여 인증을 완료해주세요.",
                is_error=True,
            )
        except google_exceptions.NotFound:
            return ToolResult(
                output="Google Cloud TTS API를 찾을 수 없습니다. 프로젝트에서 API가 활성화되었는지 확인해주세요.",
                is_error=True,
            )
        except google_exceptions.InvalidArgument as e:
            return ToolResult(
                output=f"잘못된 파라미터가 입력되었습니다. 언어 코드('{arguments.language_code}') 또는 음성 이름('{arguments.voice_name}')이 올바른지 확인해주세요. 오류: {e}",
                is_error=True,
            )
        except FileNotFoundError:
            return ToolResult(
                output=f"지정한 경로를 찾을 수 없습니다: '{arguments.output_file_path}'. 경로가 올바른지 확인해주세요.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                output=f"알 수 없는 오류가 발생했습니다: {e}",
                is_error=True,
            )
