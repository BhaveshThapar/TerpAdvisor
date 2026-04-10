import asyncio
import time
import os
import sys

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.integrations.circuit_breaker import CircuitBreaker, CircuitOpenError

async def failing_call():
    raise Exception("API Down")

async def successful_call():
    return "OK"

async def main():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
    
    print("\n--- Testing Circuit Breaker ---")
    
    # 1. Trigger failures
    for i in range(3):
        try:
            await cb.call(failing_call)
        except Exception as e:
            print(f"Call {i+1} failed as expected: {e}")
    
    # 2. Verify OPEN state
    print(f"Current state: {cb.state}")
    try:
        await cb.call(successful_call)
    except CircuitOpenError as e:
        print(f"Call 4 fast-failed as expected: {e}")
    
    # 3. Wait for recovery
    print("Waiting for recovery timeout (6s)...")
    await asyncio.sleep(6)
    print(f"Current state (should be HALF_OPEN): {cb.state}")
    
    # 4. Verify HALF_OPEN -> CLOSED
    res = await cb.call(successful_call)
    print(f"Call 5 (probe) result: {res}")
    print(f"Current state (should be CLOSED): {cb.state}")

if __name__ == "__main__":
    asyncio.run(main())
