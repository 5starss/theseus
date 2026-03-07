import os
import requests
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from app.schemas import Document as AppDocument # 우리가 정의한 문서 규격(Schema)을 가져옵니다.

# .env 파일에 저장된 API 키들을 로드합니다.
load_dotenv()

# 로깅 설정: 프로그램 실행 과정을 터미널에 출력하여 확인하기 위함입니다.
logger = logging.getLogger(__name__)

# 한국투자증권(KIS) API 접속 정보
KIS_APP_KEY = os.getenv("KIS_APP_KEY")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET")
KIS_DOMAIN = "https://openapi.koreainvestment.com:9443"
KIS_ACCESS_TOKEN = None # 한 번 발급받은 토큰은 재사용하기 위해 변수에 저장합니다.

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(BASE_DIR, "storage") # 수집한 원본 데이터를 저장할 폴더명
TOKEN_FILE = os.path.join(STORAGE_DIR, ".kis_token.json") # 토큰 캐싱 파일 경로

def get_kis_access_token() -> str:
    """
    한국투자증권(KIS) API 사용을 위한 인증 토큰(Access Token)을 발급받습니다.
    (수정) 캐시된 토큰이 있고 유효기간이 남았다면 재발급하지 않고 그대로 사용합니다.
    """
    global KIS_ACCESS_TOKEN
    
    # 1. 메모리 캐시 확인
    if KIS_ACCESS_TOKEN:
        return KIS_ACCESS_TOKEN
        
    # 2. 로컬 파일 캐시 확인 (.kis_token.json)
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token_data = json.load(f)
                expired_str = token_data.get("access_token_token_expired", "")
                
                # 만료 시간 형식: "YYYY-MM-DD HH:MM:SS"
                if expired_str:
                    expired_dt = datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
                    if datetime.now() < expired_dt:
                        KIS_ACCESS_TOKEN = token_data.get("access_token")
                        logger.info("기존 유효한 KIS Access Token을 로컬 캐시에서 불러왔습니다.")
                        return KIS_ACCESS_TOKEN
        except Exception as e:
            logger.warning(f"토큰 캐시 파일 읽기 실패 (새 발급 시도): {e}")

    # 3. 유효성 검사 실패 또는 파일 부재 시 신규 발급
    if not KIS_APP_KEY or not KIS_APP_SECRET:
        logger.error("KIS_APP_KEY 또는 KIS_APP_SECRET이 .env 파일에 설정되지 않았습니다.")
        return ""
        
    url = f"{KIS_DOMAIN}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appsecret": KIS_APP_SECRET,
        "appkey": KIS_APP_KEY
    }
    
    try:
        res = requests.post(url, headers=headers, json=body, timeout=30)
        res.raise_for_status() # 에러 발생 시 예외를 던집니다.
        data = res.json()
        KIS_ACCESS_TOKEN = data.get("access_token")
        
        # 4. 새로 발급받은 토큰 정보를 파일에 저장 (캐싱)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info("새로운 KIS Access Token 발급 및 로컬 캐싱 완료")
        return KIS_ACCESS_TOKEN
    except Exception as e:
        logger.error(f"KIS Access Token 발급 실패: {e}")
        return ""

def fetch_kis_news_title(ticker: str) -> List[Dict[str, Any]]:
    """
    특정 종목(Ticker, 예: 005930)의 최신 뉴스 제목 목록을 KIS API에서 가져옵니다.
    TR_ID 'FHKST01011800'은 '종합 시황/뉴스 제목' 조회를 의미합니다.
    """
    token = get_kis_access_token()
    if not token:
        return []
        
    url = f"{KIS_DOMAIN}/uapi/domestic-stock/v1/quotations/news-title"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": "FHKST01011800", # 뉴스 제목 조회 전용 ID
        "custtype": "P" # 개인 고객 의미
    }
    # API 요청 시 필요한 파라미터들 (명세서 기준)
    params = {
        "FID_NEWS_OFER_ENTP_CODE": "", # 전체 언론사
        "FID_COND_MRKT_CLS_CODE": "", # 전체 시장
        "FID_INPUT_ISCD": ticker,     # 종목코드 (예: 005930)
        "FID_TITL_CNTT": "",          # 제목 검색어 (비워두면 전체)
        "FID_INPUT_DATE_1": "",       # 조회 시작일
        "FID_INPUT_HOUR_1": "",       # 조회 시작 시간
        "FID_RANK_SORT_CLS_CODE": "", # 정렬 구분
        "FID_INPUT_SRNO": ""          # 입력 일련번호 (다음 페이지 조회 시용)
    }
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=30)
        res.raise_for_status()
        data = res.json()
        news_list = data.get("output", [])
        logger.info(f"KIS 뉴스 {len(news_list)}건 수집 완료 (종목코드: {ticker})")
        return news_list
    except Exception as e:
        logger.error(f"KIS 뉴스 제목 수집 실패 ({ticker}): {e}")
        return []

def save_raw_data(ticker: str, data: Dict[str, Any]):
    """
    수집한 데이터 원본을 나중에 다시 확인할 수 있도록 'storage' 폴더에 JSON 파일로 저장합니다.
    파일명에 저장 시간을 포함하여 중복을 방지합니다.
    """
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        
    file_path = os.path.join(STORAGE_DIR, f"raw_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"원본 데이터 저장 완료: {file_path}")
    return file_path

def fetch_and_store_news(ticker: str):
    """
    뉴스 수집과 저장을 한 번에 수행하는 통합 함수입니다.
    """
    logger.info(f"뉴스 수집 프로세스 시작: {ticker}")
    news_list = fetch_kis_news_title(ticker)
    
    total_data = {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {
            "news": news_list
        }
    }
    
    return save_raw_data(ticker, total_data)

def convert_to_documents(raw_data_path: str) -> List[AppDocument]:
    """
    저장된 원본(JSON) 파일을 읽어서, AI가 이해하기 쉬운 공통 규격(Document)으로 변환합니다.
    본문 내용이 없는 경우를 대비해 '뉴스 제목'을 본문에도 넣어 AI가 참고하게 합니다.
    """
    with open(raw_data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    docs = []
    ticker = raw_data.get("ticker", "UNKNOWN")
    for item in raw_data["sources"].get("news", []):
        # KIS 데이터 필드 설명:
        # data_dt: 작성일자(YYYYMMDD), data_tm: 작성시간(HHMMSS)
        # hts_pbnt_titl_cntt: 뉴스 제목 내용
        publish_dt = item.get('data_dt', '')
        publish_tm = item.get('data_tm', '')
        title = item.get('hts_pbnt_titl_cntt', '')
        
        # 날짜 형식을 '20240301' -> '2024-03-01' 형태로 보기 좋게 바꿉니다.
        if len(publish_dt) == 8:
            formatted_date = f"{publish_dt[:4]}-{publish_dt[4:6]}-{publish_dt[6:]}"
        else:
            formatted_date = publish_dt
            
        # AI 에이전트가 사용할 공통 문서 규격(AppDocument) 인스턴스를 생성합니다.
        docs.append(AppDocument(
            id=f"KIS_{item.get('cntt_usiq_srno', datetime.now().timestamp())}", # 고유 ID
            source="KIS_NEWS", # 출처 구분
            published_at=f"{formatted_date} {publish_tm}", # 발행 시각
            title=title, # 제목
            body=f"[{ticker}] {title}", # RAG에서 검색 대상으로 쓸 본문 (여기선 제목 활용)
            url="",
            source_rank=1.0 # 출처 신뢰도 점수 (1.0 만점)
        ))
    return docs
