"""
Filter Rejection Logger for v4.1.1
Tracks why each symbol is rejected and provides scan summaries
"""
import logging
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class FilterLogger:
    """Tracks filter rejections for observability and debugging"""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.rejection_counts = defaultdict(int)
        self.symbols_checked = 0
        self.symbols_passed = 0
        self.scan_start_time = None
        self.detailed_rejections: List[tuple] = []  # (symbol, reason)

    def reset_scan(self):
        """Reset counters for a new scan cycle"""
        self.rejection_counts.clear()
        self.symbols_checked = 0
        self.symbols_passed = 0
        self.detailed_rejections.clear()

    def log_rejection(self, symbol: str, reason: str, details: str = ""):
        """Log a filter rejection"""
        self.rejection_counts[reason] += 1
        self.detailed_rejections.append((symbol, reason))

        # Only log individual rejections in debug mode
        if self.debug_mode:
            if details:
                print(f"[FILTER] {symbol} rejected: {reason} ({details})")
                logger.info(f"[FILTER] {symbol} rejected: {reason} ({details})")
            else:
                print(f"[FILTER] {symbol} rejected: {reason}")
                logger.info(f"[FILTER] {symbol} rejected: {reason}")

    def log_pass(self, symbol: str):
        """Log a symbol passing all filters"""
        self.symbols_passed += 1
        if self.debug_mode:
            logger.info(f"[FILTER] {symbol} PASSED all filters ✓")

    def increment_checked(self):
        """Increment symbols checked counter"""
        self.symbols_checked += 1

    def print_scan_summary(self, signals_created: int):
        """Print comprehensive scan summary"""
        print("\n" + "=" * 60)
        print("📊 SCAN SUMMARY")
        print("=" * 60)
        print(f"Symbols checked: {self.symbols_checked}")
        print(f"Signals created: {signals_created}")
        print(f"Symbols passed filters: {self.symbols_passed}")

        if self.rejection_counts:
            print(f"\n❌ Rejection breakdown:")
            # Sort by count descending
            sorted_rejections = sorted(
                self.rejection_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for reason, count in sorted_rejections:
                print(f"  {count:3d} - {reason}")
        else:
            print("\n✅ No rejections (all symbols passed)")

        # Calculate rejection rate
        if self.symbols_checked > 0:
            rejection_rate = ((self.symbols_checked - signals_created) / self.symbols_checked) * 100
            print(f"\nRejection rate: {rejection_rate:.1f}%")

        print("=" * 60 + "\n")

    def get_rejection_stats(self) -> Dict:
        """Return rejection statistics as dict"""
        return {
            'symbols_checked': self.symbols_checked,
            'symbols_passed': self.symbols_passed,
            'rejections': dict(self.rejection_counts),
            'detailed_rejections': self.detailed_rejections
        }


# Global filter logger instance
_filter_logger: FilterLogger = None


def get_filter_logger(debug_mode: bool = False) -> FilterLogger:
    """Get or create global filter logger"""
    global _filter_logger
    if _filter_logger is None:
        _filter_logger = FilterLogger(debug_mode=debug_mode)
    return _filter_logger


def log_filter(symbol: str, reason: str, details: str = ""):
    """Convenience function to log filter rejection"""
    logger = get_filter_logger()
    logger.log_rejection(symbol, reason, details)
