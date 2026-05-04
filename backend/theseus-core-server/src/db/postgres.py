from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import settings

# 동기 엔진 생성 (기본)
engine = create_engine(
    settings.database_url,
    echo=False,  # 쿼리 로깅이 필요하면 True로 변경
    pool_pre_ping=True, # 끊어진 연결 자동 재연결
    pool_size=5,
    max_overflow=10
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 모델 클래스 생성
Base = declarative_base()


def init_db() -> None:
    """
    등록된 SQLAlchemy 모델 기준으로 필요한 테이블을 생성합니다.
    Alembic이 없는 현재 Phase 1에서는 서버 기동 시 이 함수를 호출해
    신규 모델(tool_plans 포함)을 자동 부트스트랩합니다.
    """
    import src.db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

def get_db():
    """
    FastAPI 의존성 주입용 제너레이터
    요청당 하나의 DB 세션을 제공합니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
