# app/tools.py

import logging
import json
import os

# ایمپورت لود کننده فایل (برای خواندن توضیحات ابزار)
from .db_per import load_prompt_from_file

from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# ایمپورت سرویس‌ها (CityService + get_http_client)
from .services import get_http_client, CityService, CategoryManager

logger = logging.getLogger("app.tools")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.hamyaranshahr.com")




# --------------------------------------------------------------------------- #
# بخش ۱: لود کردن توضیحات ابزار (Tool Description)
# --------------------------------------------------------------------------- #
# هدف: خواندن دستورالعمل‌های دقیق از فایل برای هدایت بهتر هوش مصنوعی

_SEARCH_DESC_PATH = os.path.join("knowledgebase", "tools", "search_booths.md")
SEARCH_BOOTHS_DESCRIPTION = load_prompt_from_file(_SEARCH_DESC_PATH)

# متن پیش‌فرض (Fallback) اگر فایل پیدا نشد
if not SEARCH_BOOTHS_DESCRIPTION:
    SEARCH_BOOTHS_DESCRIPTION = (
        "Search for businesses based on exact Category ID and Location. "
        "Use this tool when the user asks for a service like 'mechanic' or 'bakery'."
    )

# --------------------------------------------------------------------------- #
# بخش ۲: تعریف اسکیما (Schema) برای OpenAI
# --------------------------------------------------------------------------- #

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_booths",
            "description": SEARCH_BOOTHS_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "The exact Business Category ID from the system list."
                    },
                    "city_name": {
                        "type": "string",
                        # ✅ دستور صریح به مدل: خودت شهر را پیدا کن و بفرست
                        "description": "The target city name in Persian (e.g. 'اصفهان'). Always populate this field based on user input OR system location context."
                    }
                },
                # ✅ هر دو فیلد اجباری هستند
                "required": ["category_id", "city_name"]
            }
        }
    }
]

# ... (تابع _call_backend_api بدون تغییر) ...

# --------------------------------------------------------------------------- #
# بخش ۳: هندلر اصلی (ساده شده)
# --------------------------------------------------------------------------- #

async def handle_search_booths(
    category_id: int,
    city_name: str, # ✅ این الان اجباری است (چون مدل حتما میفرستد)
    user_lat: Optional[float] = None, 
    user_lon: Optional[float] = None
) -> str:
    
    # 1. اعتبارسنجی
    if not category_id:
        return json.dumps({"status": "error", "message": "Category ID is required."}, ensure_ascii=False)
    
    # اگر مدل به هر دلیلی شهر را نفرستاد (که نباید پیش بیاید)، ارور میدهیم
    if not city_name:
        return json.dumps({"status": "error", "message": "City name is required."}, ensure_ascii=False)

    # 2. دریافت Slug بیزینس
    business_slug = CategoryManager.get_slug_by_id(category_id)
    if not business_slug:
        return json.dumps({"status": "error", "message": "Invalid Category ID."}, ensure_ascii=False)

    logger.info(f"Tool Exec: CatID={category_id} ({business_slug}) | City={city_name}")

    # 3. تبدیل اسم شهر به Slug (با استفاده از CityService)
    final_city_display = city_name
    city_slug, real_name = CityService.find_city_slug(city_name)
    
    if not city_slug:
        return json.dumps({
            "status": "error",
            "message": f"City '{city_name}' not found in Isfahan province coverage."
        }, ensure_ascii=False)
    
    final_city_display = real_name

    # 4. چیدن پارامترها
    params = {
        "BusinessSlug": business_slug,
        "CitySlug": city_slug, # ✅ همیشه اسلاگ شهر را می‌فرستیم
        "PageSize": 5
    }

    # ✅ نکته مهم: ما مختصات را هم می‌فرستیم تا بک‌ند "فاصله" را حساب کند
    # حتی اگر شهر انتخاب شده، شهر کاربر نباشد (مثلاً کاربر در اصفهان است، مکانیکی در شاهین شهر می‌خواهد)
    # بک‌ند فاصله کاربر تا مکانیکی‌های شاهین شهر را حساب می‌کند که درست است.
    if user_lat and user_lon:
        params["Latitude"] = user_lat
        params["Longitude"] = user_lon

    # 5. تماس با بک‌ند
    try:
        resp = await _call_backend_api(params)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            
            if not items:
                return json.dumps({
                    "status": "success",
                    "message": f"No results found for '{business_slug}' in {final_city_display}."
                }, ensure_ascii=False)
            
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
                "city_used": final_city_display,
                "results": simplified_items
            }, ensure_ascii=False)
            
        elif resp.status_code == 404:
            return json.dumps({"status": "not_found", "message": "Nothing found."}, ensure_ascii=False)
        else:
            logger.error(f"Backend Error: {resp.status_code} - {resp.text}")
            return json.dumps({"status": "error", "code": resp.status_code}, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Tool execution error: {e}")
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)