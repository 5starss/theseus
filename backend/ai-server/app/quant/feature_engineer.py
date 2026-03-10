import logging
import numpy as np
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


class IntradayFeatureEngineer:
    """1분봉 OHLCV 데이터를 모델 학습용 기술적 지표 및 미세구조 피처로 변환합니다."""

    def __init__(self, horizon_minutes: int = 5):
        self.horizon_minutes = horizon_minutes
        self.required_cols = ["ts", "open", "high", "low", "close", "volume"]

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """와일더 방식의 RSI(Relative Strength Index)를 계산합니다."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        return 100 - (100 / (1 + rs))

    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """수익률 및 모멘텀 관련 피처를 추가합니다."""
        df["ret_1m"] = df["close"].pct_change()
        df["log_ret_1m"] = np.log(df["close"]).diff()
        df["mom_5"] = df["close"].pct_change(5)
        df["mom_15"] = df["close"].pct_change(15)
        return df

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """이동평균, MACD, 볼린저 밴드 등 전통적 기술 지표를 추가합니다."""
        # Moving Averages
        df["sma_5"] = df["close"].rolling(5).mean()
        df["sma_20"] = df["close"].rolling(20).mean()
        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # MACD
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        df["bb_mid"] = df["close"].rolling(20).mean()
        df["bb_std"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"].replace(0, np.nan)
        df["bb_pct_b"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)

        # RSI
        df["rsi_14"] = self._calc_rsi(df["close"], 14)
        return df

    def _add_volatility_and_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """변동성 및 거래량 관련 피처를 추가합니다."""
        df["vol_5"] = df["ret_1m"].rolling(5).std()
        df["vol_20"] = df["ret_1m"].rolling(20).std()
        
        # VWAP (Volume Weighted Average Price) - Intraday
        df["date"] = df["ts"].dt.date
        tp = (df["high"] + df["low"] + df["close"]) / 3
        df["cum_pv"] = (tp * df["volume"]).groupby(df["date"]).cumsum()
        df["cum_vol"] = df["volume"].groupby(df["date"]).cumsum()
        df["vwap"] = df["cum_pv"] / df["cum_vol"].replace(0, np.nan)
        df["dist_vwap"] = (df["close"] - df["vwap"]) / df["vwap"].replace(0, np.nan)

        # Volume Z-Score
        df["volume_ma20"] = df["volume"].rolling(20).mean()
        df["volume_z20"] = (df["volume"] - df["volume_ma20"]) / df["volume"].rolling(20).std().replace(0, np.nan)

        # Realized Volatility & High-order stats
        df["rv_30"] = np.sqrt(df["ret_1m"].pow(2).rolling(30).sum())
        df["skew_30"] = df["ret_1m"].rolling(30).skew()
        return df

    def _add_microstructure_and_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """가격 미세구조와 시간대 관련 피처를 추가합니다."""
        # Microstructure
        df["close_high_ratio"] = (df["close"] - df["low"]) / (df["high"] - df["low"] + 1e-8)
        df["close_low_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 1e-8)
        df["price_accel"] = df["close"].diff().diff()

        # Time
        df["minute_of_day"] = df["ts"].dt.hour * 60 + df["ts"].dt.minute
        df["session_progress"] = (df["minute_of_day"] - 540) / 390.0
        df["is_market_open_30"] = ((df["minute_of_day"] >= 540) & (df["minute_of_day"] < 570)).astype(int)
        df["is_market_close_30"] = ((df["minute_of_day"] >= 900) & (df["minute_of_day"] < 930)).astype(int)
        return df

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """모든 피처 생성 단계를 실행하고 타겟 변수를 생성합니다."""
        if df.empty: raise ValueError("데이터가 없습니다.")
        
        feat = df.copy().sort_values("ts").reset_index(drop=True)
        
        feat = self._add_momentum_features(feat)
        feat = self._add_technical_indicators(feat)
        feat = self._add_volatility_and_volume_features(feat)
        feat = self._add_microstructure_and_time_features(feat)

        # Interaction
        feat["mom_vol_interaction"] = feat["mom_5"] * feat["vol_5"]
        feat["rsi_momentum_cross"] = feat["rsi_14"] * np.sign(feat["mom_5"])

        # Target (Horizon Minutes 후의 수익률)
        feat["target_return"] = feat["close"].shift(-self.horizon_minutes) / feat["close"] - 1
        
        # Cleanup
        drop_cols = ["date", "cum_pv", "cum_vol"]
        feat = feat.drop(columns=[c for c in drop_cols if c in feat.columns])
        feat = feat.dropna().reset_index(drop=True)
        
        logger.info(f"피처 생성 완료: {len(feat)}건 | 피처 수: {len(feat.columns)}")
        return feat
