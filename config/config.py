"""
Alpha Sniper v4.1 Configuration Module
Loads all environment variables for the Sniper Swing strategy
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class for Alpha Sniper v4.1"""

    # === EXCHANGE ===
    MEXC_BASE_URL: str = os.getenv('MEXC_BASE_URL', 'https://api.mexc.com')
    VENUE: str = os.getenv('VENUE', 'MEXC')

    # === TRADING MODE ===
    MODE: str = os.getenv('MODE', 'SIM')
    SIM_EQUITY_START: float = float(os.getenv('SIM_EQUITY_START', '500'))
    LIVE_EQUITY_START: float = float(os.getenv('LIVE_EQUITY_START', '0'))

    # === STRATEGY ===
    STRATEGY: str = os.getenv('STRATEGY', 'sniper_swing')
    DIRECTION: str = os.getenv('DIRECTION', 'long_only')
    MIN_SIGNAL_SCORE: float = float(os.getenv('MIN_SIGNAL_SCORE', '65'))
    SYMBOL_COOLDOWN_HOURS: float = float(os.getenv('SYMBOL_COOLDOWN_HOURS', '12'))

    # === TIMEFRAMES ===
    USE_15M: bool = os.getenv('USE_15M', 'false').lower() == 'true'
    USE_1H: bool = os.getenv('USE_1H', 'true').lower() == 'true'
    USE_4H: bool = os.getenv('USE_4H', 'true').lower() == 'true'
    USE_24H: bool = os.getenv('USE_24H', 'true').lower() == 'true'

    # === HARD DIRECTIONAL FILTERS ===
    MIN_RET_1H_PCT: float = float(os.getenv('MIN_RET_1H_PCT', '1.0'))
    MIN_RET_4H_PCT: float = float(os.getenv('MIN_RET_4H_PCT', '2.0'))
    MIN_RET_24H_PCT: float = float(os.getenv('MIN_RET_24H_PCT', '2.0'))
    REQUIRE_SAME_DIRECTION: bool = os.getenv('REQUIRE_SAME_DIRECTION', 'true').lower() == 'true'
    MIN_RVOL_1H: float = float(os.getenv('MIN_RVOL_1H', '2.0'))
    MIN_RSI_1H: float = float(os.getenv('MIN_RSI_1H', '60'))
    MAX_RSI_1H: float = float(os.getenv('MAX_RSI_1H', '75'))
    REQUIRE_ABOVE_MA_24H_50: bool = os.getenv('REQUIRE_ABOVE_MA_24H_50', 'true').lower() == 'true'

    # === ENTRY QUALITY FILTERS (v4.1.1) ===
    REJECT_PARABOLIC_MOVES: bool = os.getenv('REJECT_PARABOLIC_MOVES', 'true').lower() == 'true'
    PARABOLIC_THRESHOLD: float = float(os.getenv('PARABOLIC_THRESHOLD', '1.5'))
    REJECT_HIGH_RANGE_ENTRIES: bool = os.getenv('REJECT_HIGH_RANGE_ENTRIES', 'true').lower() == 'true'
    MAX_RANGE_POSITION_PCT: float = float(os.getenv('MAX_RANGE_POSITION_PCT', '0.85'))
    PREFER_PULLBACKS: bool = os.getenv('PREFER_PULLBACKS', 'true').lower() == 'true'

    # === SCORING WEIGHTS ===
    WEIGHT_TREND: float = float(os.getenv('WEIGHT_TREND', '0.35'))
    WEIGHT_VOLUME: float = float(os.getenv('WEIGHT_VOLUME', '0.20'))
    WEIGHT_MA_ALIGNMENT: float = float(os.getenv('WEIGHT_MA_ALIGNMENT', '0.20'))
    WEIGHT_RSI_REGIME: float = float(os.getenv('WEIGHT_RSI_REGIME', '0.15'))
    WEIGHT_STRUCTURE: float = float(os.getenv('WEIGHT_STRUCTURE', '0.10'))

    # === RISK & EXIT ===
    RISK_PER_TRADE_PCT: float = float(os.getenv('RISK_PER_TRADE_PCT', '3.0'))
    STOP_LOSS_PCT: float = float(os.getenv('STOP_LOSS_PCT', '3.0'))
    TAKE_PROFIT_PCT: float = float(os.getenv('TAKE_PROFIT_PCT', '10.0'))
    MAX_CONCURRENT_POS: int = int(os.getenv('MAX_CONCURRENT_POSITIONS', '3'))
    MAX_DAILY_DRAWDOWN_PCT: float = float(os.getenv('MAX_DAILY_DRAWDOWN_PCT', '15.0'))

    # === TRAILING STOP ===
    USE_TRAILING_STOP: bool = os.getenv('USE_TRAILING_STOP', 'true').lower() == 'true'
    TRAILING_ACTIVATION_PCT: float = float(os.getenv('TRAILING_ACTIVATION_PCT', '4.0'))
    TRAILING_DISTANCE_PCT: float = float(os.getenv('TRAILING_DISTANCE_PCT', '1.5'))
    BREAKEVEN_AFTER_PCT: float = float(os.getenv('BREAKEVEN_AFTER_PCT', '5.0'))
    BREAKEVEN_OFFSET_PCT: float = float(os.getenv('BREAKEVEN_OFFSET_PCT', '0.1'))

    # === HOLD TIME ===
    MIN_HOLD_HOURS: float = float(os.getenv('MIN_HOLD_HOURS', '4'))
    MAX_HOLD_HOURS: float = float(os.getenv('MAX_HOLD_HOURS', '36'))
    MAX_HOLD_HOURS_FALLBACK: float = float(os.getenv('MAX_HOLD_HOURS_FALLBACK', '48'))

    # === MOON MODE ===
    MOON_SCORE_THRESHOLD: float = float(os.getenv('MOON_SCORE_THRESHOLD', '75'))
    MOON_MULTIPLIER: float = float(os.getenv('MOON_MULTIPLIER', '2.0'))

    # === UNIVERSE FILTERS ===
    MIN_LIQUIDITY_VOLUME_24H: float = float(os.getenv('MIN_LIQUIDITY_VOLUME_24H', '50000'))
    MAX_SPREAD_BPS: float = float(os.getenv('MAX_SPREAD_BPS', '50'))
    EXCLUDE_STABLECOINS: bool = os.getenv('EXCLUDE_STABLECOINS', 'true').lower() == 'true'

    # Stablecoin list
    _stablecoins_str: str = os.getenv('STABLECOINS', 'USDT,USDC,USDE,DAI,FDUSD,USD1,TUSD,PYUSD,BUSD,UST,USDD,USDP,GUSD,HUSD,SUSD,LUSD,FRAX,USDJ,USDN,USTC')
    STABLECOINS: List[str] = [s.strip() for s in _stablecoins_str.split(',')]

    # === FEES & SLIPPAGE ===
    MAKER_FEE_PCT: float = float(os.getenv('MAKER_FEE_PCT', '0.0'))
    TAKER_FEE_PCT: float = float(os.getenv('TAKER_FEE_PCT', '0.1'))
    SLIPPAGE_PCT: float = float(os.getenv('SLIPPAGE_PCT', '0.05'))

    # === CORRELATION ===
    MAX_CORRELATION_THRESHOLD: float = float(os.getenv('MAX_CORRELATION_THRESHOLD', '0.8'))
    MAX_CORRELATED_POSITIONS: int = int(os.getenv('MAX_CORRELATED_POSITIONS', '2'))

    # === TELEGRAM ===
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    ALERT_ON_DRAWDOWN_PCT: float = float(os.getenv('ALERT_ON_DRAWDOWN_PCT', '10.0'))
    ALERT_ON_POSITION_OPEN: bool = os.getenv('ALERT_ON_POSITION_OPEN', 'true').lower() == 'true'
    ALERT_ON_POSITION_CLOSE: bool = os.getenv('ALERT_ON_POSITION_CLOSE', 'true').lower() == 'true'
    DAILY_REPORT_HOUR: int = int(os.getenv('DAILY_REPORT_HOUR', '9'))

    # === SCHEDULER ===
    SCANNER_INTERVAL: int = int(os.getenv('SCANNER_INTERVAL', '300'))
    TRADER_INTERVAL: int = int(os.getenv('TRADER_INTERVAL', '60'))
    LEARNING_INTERVAL: int = int(os.getenv('LEARNING_INTERVAL', '3600'))

    # === ADVANCED ===
    TRADING_PAUSED: bool = os.getenv('TRADING_PAUSED', 'false').lower() == 'true'
    CHECK_ORDER_BOOK_IMBALANCE: bool = os.getenv('CHECK_ORDER_BOOK_IMBALANCE', 'false').lower() == 'true'
    LEARNING_ENABLED: bool = os.getenv('LEARNING_ENABLED', 'false').lower() == 'true'
    MIN_TRADES_FOR_LEARNING: int = int(os.getenv('MIN_TRADES_FOR_LEARNING', '50'))
    MAX_WEIGHT_CHANGE_PCT: float = float(os.getenv('MAX_WEIGHT_CHANGE_PCT', '15'))
    LEARNING_LOOKBACK_DAYS: int = int(os.getenv('LEARNING_LOOKBACK_DAYS', '30'))

    # === DATA & LOGGING ===
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'data/trades.db')
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_TO_FILE: bool = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    LOG_DIR: str = os.getenv('LOG_DIR', 'logs')
    MAX_LOG_SIZE_MB: int = int(os.getenv('MAX_LOG_SIZE_MB', '10'))
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration values"""
        # Ensure weights sum to ~1.0
        total_weight = (cls.WEIGHT_TREND + cls.WEIGHT_VOLUME +
                       cls.WEIGHT_MA_ALIGNMENT + cls.WEIGHT_RSI_REGIME +
                       cls.WEIGHT_STRUCTURE)
        if abs(total_weight - 1.0) > 0.01:
            print(f"⚠️ Warning: Scoring weights sum to {total_weight:.3f}, expected 1.0")

        # Ensure 15m is disabled
        if cls.USE_15M:
            print("⚠️ Warning: USE_15M=true violates anti-scalping design. Setting to false.")
            cls.USE_15M = False

        # Ensure required timeframes are enabled
        if not (cls.USE_1H and cls.USE_4H and cls.USE_24H):
            raise ValueError("❌ v4.1 requires USE_1H, USE_4H, and USE_24H to be true")


# Global config instance
config = Config()

# Validate on import
config.validate()
