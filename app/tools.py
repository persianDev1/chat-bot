# app/tools.py

import logging
import json
import os
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# ایمپورت سرویس‌ها (GeoService + get_http_client)
from .services import GeoService, get_http_client

logger = logging.getLogger("app.tools")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.hamyaranshahr.com")

# --------------------------------------------------------------------------- #
# بخش ۱: تعریف Schema ابزار
# --------------------------------------------------------------------------- #
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_booths",
            "description": "Search for businesses based on exact Category ID and Location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "The exact Business Category ID from the system list."
                    },
                    "city_name": {
                        "type": "string",
                        "description": "City name (e.g. 'Tehran')."
                    }
                },
                "required": ["category_id"]
            }
        }
    }
]

# --------------------------------------------------------------------------- #
# بخش ۲: توابع کمکی (Helper Functions)
# --------------------------------------------------------------------------- #

@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
async def _call_backend_api(params: dict) -> httpx.Response:
    """
    تابع داخلی برای تماس با بک‌ند با قابلیت Retry و استفاده از کلاینت اشتراکی.
    """
    client = await get_http_client()
    url = f"{API_BASE_URL}/api/booths"
    return await client.get(url, params=params)

# --------------------------------------------------------------------------- #
# بخش ۳: تابع اجرایی اصلی (The Handler)
# --------------------------------------------------------------------------- #

async def handle_search_booths(
    category_id: int,
    city_name: Optional[str] = None,
    user_lat: Optional[float] = None, 
    user_lon: Optional[float] = None
) -> str:
    """
    اجرای جستجو با اعتبارسنجی ورودی و مدیریت خطای پیشرفته.
    """
    
    # 1. اعتبارسنجی ورودی (Validation)
    if not category_id:
        return json.dumps({
            "status": "error",
            "message": "Category ID is required and cannot be zero."
        }, ensure_ascii=False)

    logger.info(f"Tool Exec: cat_id={category_id}, city='{city_name}', lat={user_lat}")

    # 2. حل کردن مسئله شهر (City Resolution)
    final_city = city_name

    # اگر شهر متنی نبود ولی مختصات داشتیم -> تبدیل مختصات
    if not final_city and user_lat and user_lon:
        logger.info("Resolving city from coordinates...")
        detected_city = await GeoService.get_city_from_coords(user_lat, user_lon)
        if detected_city:
            final_city = detected_city
            logger.info(f"City resolved: {final_city}")

    # 3. آماده‌سازی پارامترها
    params = {
        "BusinessCategoryId": category_id,
        "PageSize": 5 
    }
    
    if final_city:
        logger.info(f"City provided: {final_city}")
        params["CitySlug"] = final_city

    # 4. ارسال درخواست به بک‌ند
    try:
        resp = await _call_backend_api(params)
        
        # مدیریت کدهای وضعیت مختلف (Error Handling)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            
            if not items:
                return json.dumps({
                    "status": "success",
                    "message": f"No results found for Category ID {category_id} in '{final_city or 'all cities'}'."
                }, ensure_ascii=False)
            
            # خلاصه کردن نتیجه (Mapping)
            simplified_items = []
            for item in items:
                simplified_items.append({
                    "name": item.get("displayName"),
                    "category": item.get("businessCategoryName"),
                    "phone": item.get("phoneNumber"),
                    "address": item.get("address"),
                    "city": item.get("cityName"),
                    "map_link": f"https://www.google.com/maps?q={item.get('latitude')},{item.get('longitude')}"
                })
            
            return json.dumps({
                "status": "success",
                "city_used": final_city,
                "results": simplified_items
            }, ensure_ascii=False)
            
        elif resp.status_code == 404:
            return json.dumps({
                "status": "error",
                "message": "The requested city or category was not found in the system."
            }, ensure_ascii=False)
            
        elif resp.status_code >= 500:
            logger.error(f"Backend Server Error: {resp.status_code}")
            return json.dumps({
                "status": "error",
                "message": "Temporary backend system error. Please try again later."
            }, ensure_ascii=False)
            
        else:
            logger.error(f"API Error: {resp.status_code} - {resp.text}")
            return json.dumps({
                "status": "error", 
                "code": resp.status_code,
                "message": "Unknown API error"
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Tool execution exception: {e}")
        return json.dumps({
            "status": "error", 
            "message": f"Internal Tool Error: {str(e)}"
        }, ensure_ascii=False)