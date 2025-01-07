from functools import wraps
import pybreaker

# Simple circuit breakers for each service
mongodb_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
nats_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

def with_circuit_breaker(breaker):
    """Simple decorator to wrap functions with circuit breaker"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator