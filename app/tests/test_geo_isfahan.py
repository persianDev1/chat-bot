import asyncio
import os
from geopy.geocoders import Nominatim
from app.services import GeoService

# مختصات تست در استان اصفهان
LOCATIONS = [
    {
        "name": "📍 اصفهان - میدان نقش جهان",
        "lat": 32.6577, 
        "lon": 51.6776
    },
    {
        "name": "📍 نجف‌آباد (مرکز شهر)",
        "lat": 32.6332, 
        "lon": 51.3673
    },
    {
        "name": "📍 شاهین‌شهر",
        "lat": 32.8645, 
        "lon": 51.5552
    },
    {
        "name": "📍 فلاورجان",
        "lat": 32.5564, 
        "lon": 51.5122
    },
    {
        "name": "📍 روستای ابیانه (تست روستا)",
        "lat": 33.5857, 
        "lon": 51.5929
    }
]

async def run_detailed_test():
    print("--- 🌍 شروع تست دقیق مکان‌یابی در اصفهان ---")
    
    # یک کلاینت موقت برای دیدن دیتای خام
    debug_geo = Nominatim(user_agent="debug_script_isfahan", timeout=15)

    for loc in LOCATIONS:
        print(f"\n🔎 تست: {loc['name']}")
        print(f"   مختصات: {loc['lat']}, {loc['lon']}")
        
        # 1. گرفتن دیتای خام (برای اینکه ببینی چه خبره)
        raw_data = debug_geo.reverse((loc['lat'], loc['lon']), language='fa', exactly_one=True)
        address = raw_data.raw.get('address', {})
        
        print("   📦 دیتای خام دریافتی از نقشه:")
        # فیلدهای مهم را چاپ می‌کنیم
        print(f"      👉 city: {address.get('city')}")
        print(f"      👉 town: {address.get('town')}")
        print(f"      👉 county: {address.get('county')}")
        print(f"      👉 village: {address.get('village')}")
        print(f"      👉 state: {address.get('state')}")

        # 2. تست سرویس اصلی خودمان (با لاجیک تمیزکاری)
        detected_city = await GeoService.get_city_from_coords(loc['lat'], loc['lon'])
        print(f"   ✅ خروجی نهایی سرویس ما: [{detected_city}]")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_detailed_test())