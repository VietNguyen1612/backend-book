import time

class RateLimiter:
    def __init__(self, max_requests: int, time_window_seconds: int):
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        # TODO: Initialize your state storage here

    def is_allowed(self, client_id: str) -> bool:
        # TODO: Implement rate limiting logic
        # Return True if request is allowed, False if rate limited
        pass

# Test your implementation
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=2, time_window_seconds=10)
    print(limiter.is_allowed("user1")) # True
    print(limiter.is_allowed("user1")) # True
    print(limiter.is_allowed("user1")) # False
