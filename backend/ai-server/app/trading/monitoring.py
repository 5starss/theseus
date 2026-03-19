import logging
from typing import Optional, Dict
from decimal import Decimal

from app.shared.infra.redis_client import redis_client

logger = logging.getLogger(__name__)

def get_current_price(ticker: str) -> Optional[Decimal]:
    """
    Redis에서 해당 종목의 실시간 체결가(Price)를 조회합니다.
    
    조회 우선순위:
    1) stocks:current:{ticker} -> price (실시간 체결가)
    2) stocks:info:{ticker} -> currentPrice (전일 종가 또는 현재가 fallback)
    """
    r = redis_client.get_client()
    
    try:
        # 1순위: stocks:current (Hash)
        current_key = f"stocks:current:{ticker}"
        price_str = r.hget(current_key, "price")
        
        if price_str:
            return Decimal(str(price_str))
            
        # 2순위: stocks:info (Hash) - Fallback
        info_key = f"stocks:info:{ticker}"
        price_str = r.hget(info_key, "currentPrice")
        
        if price_str:
            return Decimal(str(price_str))
            
        return None
        
    except Exception as e:
        logger.error(f"Redis 시세 조회 실패 ({ticker}): {e}")
        return None

def monitor_tickers(tickers: Dict[str, Dict[str, Decimal]]):
    """
    지정된 종목들의 시세를 모니터링합니다.
    tickers: { 'ticker': { 'target_buy': 204000, 'stop_loss': 199000, 'take_profit': 215000 } }
    
    현재는 시세 조회 기능 위주로 구현되어 있으며, 
    추후 주문 로직(Orchestrator 연동)이 추가될 예정입니다.
    """
    logger.info(f"실시간 모니터링 시작: {list(tickers.keys())}")
    
    for ticker, strategy in tickers.items():
        current_price = get_current_price(ticker)
        if current_price:
            logger.info(f"[{ticker}] 현재가: {current_price:,} | 전략: {strategy}")
            
            # TODO: 전략 매칭 및 주문 로직 구현 (Phase 4 후반부)
        else:
            logger.warning(f"[{ticker}] 시세 데이터를 가져올 수 없습니다.")

if __name__ == "__main__":
    # 테스트용 코드 (로컬 실행 시)
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO)
    
    # 예시 종목 (삼성전자 등)
    test_tickers = {
        "005930": {"target_buy": Decimal("71000"), "stop_loss": Decimal("69000"), "take_profit": Decimal("75000")}
    }
    
    monitor_tickers(test_tickers)
