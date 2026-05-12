# 빌드 스테이지
FROM python:3.11-slim as builder

WORKDIR /app

# 시스템 의존성 (필요한 경우)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 환경 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 런타임 스테이지
FROM python:3.11-slim as runtime

# 보안: non-root 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 빌더 스테이지에서 설치된 패키지 복사
COPY --from=builder /root/.local /home/appuser/.local

# PATH 업데이트
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 소스 코드 복사
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser theseus_engine/ ./theseus_engine/
RUN python -m compileall src theseus_engine
# 설정 파일 등 복사 (필요시)
# COPY --chown=appuser:appuser .env.example ./.env.example

# 사용자 전환
USER appuser

EXPOSE 8086

# 헬스체크 추가 (선택사항)
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8086/health')" || exit 1

# 실행 명령 (uvicorn 사용)
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8086", "--workers", "1"]
