import asyncio
import httpx
import time

async def hit_rec(client, i):
    start = time.time()
    resp = await client.post("http://localhost:8000/api/recommendations", json={
        "major": "Computer Science",
        "completed": ["CMSC131", "MATH140"],
        "weights": {"GPA": 0.5, "Requirement Fulfillment": 0.5},
        "filters": {"levels": [100]}
    })
    end = time.time()
    return i, resp.status_code, end - start

async def main():
    async with httpx.AsyncClient() as client:
        tasks = [hit_rec(client, i) for i in range(25)]
        results = await asyncio.gather(*tasks)
        for i, status, duration in results:
            print(f"Req {i}: Status {status}, Duration {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
