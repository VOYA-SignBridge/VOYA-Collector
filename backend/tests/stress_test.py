import asyncio
import aiohttp
import time
import argparse
import sys

async def fetch(session, url):
    try:
        async with session.get(url, timeout=5) as response:
            return response.status
    except Exception:
        return 0

async def bound_fetch(sem, session, url):
    async with sem:
        return await fetch(session, url)

async def run_stress_test(base_url, duration, connections):
    print(f"🚀 Bắt đầu quá trình Stress Test cực hạn trên {base_url}")
    print(f"🔥 Số kết nối đồng thời: {connections}, Thời gian: {duration} giây")
    print("-" * 50)
    
    endpoints = [
        f"{base_url}/metrics",
        f"{base_url}/api/v1/health"
    ]
    
    start_time = time.time()
    end_time = start_time + duration
    
    success_count = 0
    error_count = 0
    
    sem = asyncio.Semaphore(connections)
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=connections)) as session:
        tasks = set()
        
        while time.time() < end_time:
            # Keep queue filled up to `connections` amount
            while len(tasks) < connections and time.time() < end_time:
                for url in endpoints:
                    task = asyncio.create_task(bound_fetch(sem, session, url))
                    tasks.add(task)
            
            # Wait for at least one task to finish
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks = pending
            
            for task in done:
                status = task.result()
                if status == 200:
                    success_count += 1
                else:
                    error_count += 1

    elapsed = time.time() - start_time
    total = success_count + error_count
    rate = total / elapsed if elapsed > 0 else 0
    
    print("\n--- 📊 Kết Quả Stress Test ---")
    print(f"⏱️ Tổng thời gian: {elapsed:.2f} giây")
    print(f"📦 Tổng số Request: {total}")
    print(f"✅ Thành công (HTTP 200): {success_count}")
    print(f"❌ Thất bại/Nghẽn: {error_count}")
    print(f"⚡ Tốc độ (RPS): {rate:.2f} req/s")
    print("👉 Hãy mở Grafana (chỉnh thời gian 5 phút gần nhất & Auto-Refresh 5s) để xem biểu đồ Request Rate và CPU nhảy vọt!")

def main():
    parser = argparse.ArgumentParser(description="Mega Stress Test script for VOYA-Collector")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the backend")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--connections", type=int, default=1000, help="Number of concurrent users/connections")
    
    args = parser.parse_args()
    
    # Required for Windows if running inside powershell
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(run_stress_test(args.url, args.duration, args.connections))
    except KeyboardInterrupt:
        print("\nĐã dừng Stress Test.")

if __name__ == "__main__":
    main()
