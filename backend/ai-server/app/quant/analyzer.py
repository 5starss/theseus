"""
기술적 지표(Technical Indicators) 분석 엔진 모듈.

OHLCV 데이터를 입력받아 RSI, 이동평균선, 볼린저 밴드, MACD, 변동성 등
핵심 기술적 지표를 계산하고, LLM이 해석할 수 있는 요약 텍스트를 생성합니다.
"""
import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    주가 시계열 데이터에 대한 기술적 분석을 수행하는 엔진입니다.
    각 지표는 개별 메서드로 구현되어 있으며, `run_full_analysis()`를 호출하면
    모든 지표를 한번에 계산하여 딕셔너리로 반환합니다.
    """

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: OHLCV DataFrame (컬럼: open, high, low, close, volume / 인덱스: date)
        """
        if df.empty:
            raise ValueError("분석할 데이터가 비어 있습니다.")
        self.df = df.copy()
        logger.info(f"TechnicalAnalyzer 초기화 완료: {len(df)}건의 데이터 로드됨")

    # ──────────────────────────────────────────────
    # 1. 이동평균선 (Moving Averages)
    # ──────────────────────────────────────────────
    def calc_moving_averages(self) -> Dict[str, Any]:
        """
        단기(5일), 중기(20일), 장기(60일) 이동평균선을 계산합니다.
        골든크로스/데드크로스 신호도 함께 판별합니다.

        Returns:
            dict: 각 이동평균 값과 추세 신호
        """
        close = self.df["close"]

        ma5 = close.rolling(window=5).mean()
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()

        # 최신 값 추출
        latest_ma5 = ma5.iloc[-1]
        latest_ma20 = ma20.iloc[-1]
        latest_close = close.iloc[-1]

        # 골든크로스 / 데드크로스 판별
        if len(ma5.dropna()) >= 2 and len(ma20.dropna()) >= 2:
            prev_diff = ma5.dropna().iloc[-2] - ma20.dropna().iloc[-2]
            curr_diff = latest_ma5 - latest_ma20
            if prev_diff < 0 and curr_diff > 0:
                cross_signal = "골든크로스 (단기 이평선이 중기 이평선을 상향 돌파 → 매수 신호)"
            elif prev_diff > 0 and curr_diff < 0:
                cross_signal = "데드크로스 (단기 이평선이 중기 이평선을 하향 돌파 → 매도 신호)"
            else:
                cross_signal = "크로스 미발생"
        else:
            cross_signal = "데이터 부족으로 판별 불가"

        # 현재가 대비 이평선 위치 판별
        if latest_close > latest_ma5 > latest_ma20:
            position = "정배열 (상승 추세)"
        elif latest_close < latest_ma5 < latest_ma20:
            position = "역배열 (하락 추세)"
        else:
            position = "혼조세 (추세 불명확)"

        return {
            "MA5": int(latest_ma5),
            "MA20": int(latest_ma20),
            "MA60": int(ma60.iloc[-1]) if not np.isnan(ma60.iloc[-1]) else "데이터 부족",
            "현재가": int(latest_close),
            "배열_상태": position,
            "크로스_신호": cross_signal,
        }

    # ──────────────────────────────────────────────
    # 2. RSI (Relative Strength Index)
    # ──────────────────────────────────────────────
    def calc_rsi(self, period: int = 14) -> Dict[str, Any]:
        """
        RSI(상대강도지수)를 계산합니다.
        - RSI > 70: 과매수 구간 (가격 하락 가능성)
        - RSI < 30: 과매도 구간 (가격 상승 가능성)

        Args:
            period: RSI 계산 기간 (기본: 14일)

        Returns:
            dict: RSI 값과 해석
        """
        delta = self.df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        latest_rsi = rsi.iloc[-1]

        if latest_rsi >= 70:
            interpretation = f"과매수 구간 (RSI {latest_rsi:.1f}) → 단기 조정 가능성 높음"
        elif latest_rsi <= 30:
            interpretation = f"과매도 구간 (RSI {latest_rsi:.1f}) → 반등 가능성 높음"
        elif latest_rsi >= 50:
            interpretation = f"중립~강세 구간 (RSI {latest_rsi:.1f}) → 상승 모멘텀 유지"
        else:
            interpretation = f"중립~약세 구간 (RSI {latest_rsi:.1f}) → 하락 모멘텀 감지"

        return {
            "RSI_14": round(latest_rsi, 2),
            "해석": interpretation,
        }

    # ──────────────────────────────────────────────
    # 3. 볼린저 밴드 (Bollinger Bands)
    # ──────────────────────────────────────────────
    def calc_bollinger_bands(self, window: int = 20, num_std: float = 2.0) -> Dict[str, Any]:
        """
        볼린저 밴드를 계산합니다.
        - 상단 밴드 근접/돌파: 과매수
        - 하단 밴드 근접/돌파: 과매도
        - 밴드 폭(Bandwidth): 변동성 지표

        Args:
            window: 이동평균 기간 (기본: 20일)
            num_std: 표준편차 배수 (기본: 2.0)

        Returns:
            dict: 볼린저 밴드 값과 현재가 위치
        """
        close = self.df["close"]
        middle = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()

        upper = middle + (std * num_std)
        lower = middle - (std * num_std)

        latest_close = close.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_middle = middle.iloc[-1]

        # 밴드 폭 (Bandwidth) = (상단 - 하단) / 중간
        bandwidth = (latest_upper - latest_lower) / latest_middle * 100

        # 현재가의 밴드 내 위치 (%B)
        percent_b = (latest_close - latest_lower) / (latest_upper - latest_lower) * 100

        if percent_b >= 80:
            position = "상단 밴드 근접 (과매수 가능)"
        elif percent_b <= 20:
            position = "하단 밴드 근접 (과매도 가능)"
        else:
            position = "밴드 중앙 부근 (중립)"

        return {
            "상단밴드": int(latest_upper),
            "중심선": int(latest_middle),
            "하단밴드": int(latest_lower),
            "현재가": int(latest_close),
            "밴드폭(%)": round(bandwidth, 2),
            "%B": round(percent_b, 2),
            "위치_해석": position,
        }

    # ──────────────────────────────────────────────
    # 4. MACD (Moving Average Convergence Divergence)
    # ──────────────────────────────────────────────
    def calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Any]:
        """
        MACD와 시그널선을 계산합니다.
        - MACD > Signal: 매수 신호
        - MACD < Signal: 매도 신호
        - 히스토그램: 추세 강도

        Args:
            fast: 단기 EMA 기간 (기본: 12)
            slow: 장기 EMA 기간 (기본: 26)
            signal: 시그널선 기간 (기본: 9)

        Returns:
            dict: MACD, 시그널, 히스토그램 값과 해석
        """
        close = self.df["close"]

        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        latest_macd = macd_line.iloc[-1]
        latest_signal = signal_line.iloc[-1]
        latest_hist = histogram.iloc[-1]

        # 신호 판별
        if latest_macd > latest_signal and latest_hist > 0:
            interpretation = "매수 신호 (MACD가 시그널선 위에 위치, 히스토그램 양수)"
        elif latest_macd < latest_signal and latest_hist < 0:
            interpretation = "매도 신호 (MACD가 시그널선 아래에 위치, 히스토그램 음수)"
        else:
            interpretation = "전환 구간 (추세 변화 가능성)"

        return {
            "MACD": round(latest_macd, 2),
            "시그널": round(latest_signal, 2),
            "히스토그램": round(latest_hist, 2),
            "해석": interpretation,
        }

    # ──────────────────────────────────────────────
    # 5. 변동성 지표 (Volatility)
    # ──────────────────────────────────────────────
    def calc_volatility(self) -> Dict[str, Any]:
        """
        주가 변동성을 계산합니다.
        - 20일 히스토리컬 변동성 (연환산)
        - 최근 5일 수익률 통계

        Returns:
            dict: 변동성 관련 지표
        """
        close = self.df["close"]
        daily_returns = close.pct_change().dropna()

        # 20일 히스토리컬 변동성 (연환산: × √252)
        vol_20d = daily_returns.rolling(20).std().iloc[-1] * np.sqrt(252) * 100

        # 최근 5일 수익률 통계
        recent_5d = daily_returns.tail(5)
        total_return_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 5 else 0

        # 최대 낙폭 (Max Drawdown)
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative / running_max - 1) * 100
        max_drawdown = drawdown.min()

        return {
            "20일_변동성(연환산%)": round(vol_20d, 2),
            "최근5일_누적수익률(%)": round(total_return_5d, 2),
            "최근5일_일평균수익률(%)": round(recent_5d.mean() * 100, 4),
            "최대_낙폭(MDD%)": round(max_drawdown, 2),
        }

    # ──────────────────────────────────────────────
    # 6. 거래량 분석 (Volume Analysis)
    # ──────────────────────────────────────────────
    def calc_volume_analysis(self) -> Dict[str, Any]:
        """
        거래량 관련 분석을 수행합니다.
        - 20일 평균 거래량 대비 최근 거래량
        - 거래량 급증/감소 여부

        Returns:
            dict: 거래량 분석 결과
        """
        volume = self.df["volume"]

        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        latest_vol = volume.iloc[-1]

        vol_ratio = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        if vol_ratio >= 2.0:
            interpretation = f"거래량 급증 ({vol_ratio:.1f}배) → 강한 매수/매도 세력 유입"
        elif vol_ratio >= 1.5:
            interpretation = f"거래량 증가 ({vol_ratio:.1f}배) → 시장 관심 증가"
        elif vol_ratio <= 0.5:
            interpretation = f"거래량 감소 ({vol_ratio:.1f}배) → 관망세, 변동성 축소"
        else:
            interpretation = f"거래량 보통 ({vol_ratio:.1f}배) → 평상시 수준"

        return {
            "최근_거래량": f"{latest_vol:,}",
            "20일_평균_거래량": f"{int(avg_vol_20):,}",
            "거래량_비율": round(vol_ratio, 2),
            "해석": interpretation,
        }

    # ──────────────────────────────────────────────
    # 전체 분석 실행 (통합)
    # ──────────────────────────────────────────────
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        모든 기술적 지표 분석을 실행하고 결과를 하나의 딕셔너리로 반환합니다.

        Returns:
            dict: {
                "이동평균선": { ... },
                "RSI": { ... },
                "볼린저밴드": { ... },
                "MACD": { ... },
                "변동성": { ... },
                "거래량": { ... },
                "데이터_요약": { ... },
            }
        """
        logger.info("전체 기술적 지표 분석을 시작합니다...")

        results = {
            "이동평균선": self.calc_moving_averages(),
            "RSI": self.calc_rsi(),
            "볼린저밴드": self.calc_bollinger_bands(),
            "MACD": self.calc_macd(),
            "변동성": self.calc_volatility(),
            "거래량": self.calc_volume_analysis(),
            "데이터_요약": {
                "분석_기간": f"{self.df.index[0].strftime('%Y-%m-%d')} ~ {self.df.index[-1].strftime('%Y-%m-%d')}",
                "총_데이터수": len(self.df),
                "시작가": int(self.df['close'].iloc[0]),
                "최종가": int(self.df['close'].iloc[-1]),
                "기간_수익률(%)": round(
                    (self.df['close'].iloc[-1] / self.df['close'].iloc[0] - 1) * 100, 2
                ),
            },
        }

        logger.info("전체 기술적 지표 분석 완료!")
        return results

    def format_for_llm(self, analysis: Dict[str, Any]) -> str:
        """
        분석 결과를 LLM이 해석하기 좋은 구조화된 텍스트로 변환합니다.

        Args:
            analysis: run_full_analysis()의 반환값

        Returns:
            str: 구조화된 분석 리포트 문자열
        """
        lines = []
        lines.append("=" * 50)
        lines.append("📊 기술적 지표 분석 리포트")
        lines.append("=" * 50)

        for section_name, section_data in analysis.items():
            lines.append(f"\n▶ [{section_name}]")
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    lines.append(f"  • {key}: {value}")
            else:
                lines.append(f"  {section_data}")

        lines.append("\n" + "=" * 50)
        return "\n".join(lines)
