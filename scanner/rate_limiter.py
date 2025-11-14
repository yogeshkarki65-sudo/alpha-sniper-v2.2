import time
from datetime import datetime, timedelta

class RateLimiter:
    """
    Rate limiter for MEXC API to prevent bans.
    MEXC limit: 1200 requests per minute
    """
    def __init__(self, max_requests_per_minute=1000):
        self.max_requests = max_requests_per_minute
        self.requests = []
        self.weight_used = 0
        self.last_check = datetime.now()

    def check_limit(self, weight=1):
        """Check if we can make a request without exceeding rate limit."""
        now = datetime.now()

        # Clean up requests older than 1 minute
        cutoff = now - timedelta(minutes=1)
        self.requests = [r for r in self.requests if r > cutoff]

        # Check if we would exceed limit
        if len(self.requests) + weight >= self.max_requests:
            sleep_time = 60 - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                print(f"⚠️  Rate limit approaching, sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
                # Clean up after sleep
                self.requests = []

        # Record this request
        self.requests.extend([now] * weight)

    def check_weight(self, response_headers):
        """
        Check MEXC API weight from response headers.
        If weight > 900, sleep to avoid ban.
        """
        try:
            weight = int(response_headers.get("X-MEXC-USED-WEIGHT", 0))
            self.weight_used = weight

            if weight > 900:
                print(f"🚨 API weight critical ({weight}/1000), sleeping 60s")
                time.sleep(60)
                self.weight_used = 0
            elif weight > 700:
                print(f"⚠️  API weight high ({weight}/1000)")

            return weight
        except Exception as e:
            print(f"Error checking API weight: {e}")
            return 0

# Global rate limiter instance
rate_limiter = RateLimiter(max_requests_per_minute=1000)
