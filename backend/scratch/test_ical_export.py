import httpx
import asyncio

async def main():
    payload = {
        "course_ids": ["CMSC131"],
        "max_results": 1,
        "preferences": {}
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8000/api/schedule/export/ical", json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        print(f"Content-Disposition: {resp.headers.get('content-disposition')}")
        print("\nFirst 10 lines of body:")
        lines = resp.text.split("\r\n")
        for line in lines[:10]:
            print(line)

if __name__ == "__main__":
    asyncio.run(main())
