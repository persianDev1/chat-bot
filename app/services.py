# app/services.py ────────────────────────────────────────────────────────────

import logging
import asyncio
import os
import time
from typing import Optional

# کتابخانه‌های شبکه و فایل
import httpx
import aiofiles

# کتابخانه‌ جستجوی فازی
from thefuzz import process

# کتابخانه‌های موقعیت‌یابی
# from geopy.geocoders import Nominatim
# from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# کتابخانه برای مدیریت تلاش مجدد (Retry)
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("app.services")

# --------------------------------------------------------------------------- #
# بخش ۱: تنظیمات و ثابت‌ها
# --------------------------------------------------------------------------- #

# آدرس پایه API بک‌ند دات‌نت
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.hamyaranshahr.com")

# بازه زمانی آپدیت لیست دسته‌بندی‌ها (ثانیه)
CATEGORY_REFRESH_INTERVAL = int(os.getenv("CATEGORY_REFRESH_INTERVAL", "3600"))

# مسیر ذخیره‌سازی فایل کش (برای حالت آفلاین/فال‌بک)
CATEGORIES_FILE_PATH = os.path.join("knowledgebase", "categories_cache.txt")

# مسیر فایل جیسون شهرها
CITIES_JSON_PATH = os.path.join("knowledgebase", "cities.json")

# آیدی استان هدف (اصفهان)
TARGET_PROVINCE_ID = 4
# --------------------------------------------------------------------------- #
# بخش ۲: مدیریت کلاینت HTTP مشترک (Singleton Pattern)
# --------------------------------------------------------------------------- #
# هدف: جلوگیری از ایجاد کانکشن‌های متعدد و سربار TCP Handshake.
# تمام درخواست‌های برنامه از این کلاینت واحد عبور می‌کنند.

_shared_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """
    دریافت کلاینت HTTP سراسری.
    اگر کلاینت وجود نداشته باشد یا بسته شده باشد، یک نمونه جدید می‌سازد.
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=15.0)
    return _shared_client

async def close_http_client():
    """
    بستن کلاینت هنگام خاموش شدن برنامه برای جلوگیری از نشت حافظه.
    """
    global _shared_client
    if _shared_client:
        await _shared_client.aclose()
        _shared_client = None





# --------------------------------------------------------------------------- #
# 1. سرویس مدیریت شهرها (CityService) - تبدیل نام به ID
# --------------------------------------------------------------------------- #
# در فایل app/services.py

class CityService:
    """
    وظیفه: بارگذاری لیست شهرها و تبدیل نام ورودی (حتی اشتباه) به اسلاگ شهر (CitySlug).
    """
    # مپ جدید: { "نجف آباد": "نجف-آباد", "اصفهان": "اصفهان" }
    _cities_map = {}   
    _city_names = []   # لیست نام‌ها برای جستجوی فازی

    @classmethod
    def load_cities(cls):
        """در استارتاپ اجرا می‌شود تا فایل جیسون را بخواند."""
        try:
            if not os.path.exists(CITIES_JSON_PATH):
                logger.error(f"Cities file missing: {CITIES_JSON_PATH}")
                return

            with open(CITIES_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_cities = data.get('cities', [])
                
                # فیلتر: فقط شهرهای استان اصفهان
                valid_cities = [
                    city for city in all_cities 
                    if city.get('provinceId') == TARGET_PROVINCE_ID
                ]
                
                # ✅ تغییر مهم: ذخیره 'slug' به جای 'id'
                cls._cities_map = {city['name']: city['slug'] for city in valid_cities}
                cls._city_names = list(cls._cities_map.keys())
                
                logger.info(f"CityService loaded {len(valid_cities)} cities (Slugs) for Province {TARGET_PROVINCE_ID}.")
                
        except Exception as e:
            logger.error(f"Error loading cities: {e}")

    @classmethod
    # ✅ تغییر نام تابع و نوع خروجی به str
    def find_city_slug(cls, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        ورودی: نام شهر (مثلاً 'شهرستان نجف اباد')
        خروجی: (CitySlug, RealName) -> ("نجف-آباد", "نجف آباد")
        """
        if not user_input or not cls._cities_map:
            return None, None

        # 1. تمیزکاری متن
        clean = user_input.replace("ي", "ی").replace("ك", "ک")
        clean = clean.replace("شهرستان", "").replace("بخش", "").strip()

        # 2. جستجوی دقیق
        if clean in cls._cities_map:
            return cls._cities_map[clean], clean

        # 3. جستجوی فازی (thefuzz)
        extract = process.extractOne(clean, cls._city_names)
        if extract:
            best_match, score = extract
            if score >= 85:
                # ✅ برگرداندن اسلاگ
                found_slug = cls._cities_map[best_match]
                logger.info(f"Fuzzy match: '{user_input}' -> '{best_match}' (Slug: {found_slug})")
                return found_slug, best_match

        return None, None





# --------------------------------------------------------------------------- #
# بخش ۳: سرویس مدیریت دسته‌بندی‌ها (Category Manager)
# --------------------------------------------------------------------------- #
# وظایف:
# ۱. دریافت لیست خدمات (Business) از API.
# ۲. ذخیره نسخه خام (JSON) در فایل برای پایداری (Source of Truth).
# ۳. ساخت دو نسخه از داده‌ها در حافظه RAM:
#    الف) متن پرامپت (ID + Name) برای هوش مصنوعی.
#    ب) دیکشنری ترجمه (ID -> Slug) برای ارسال به بک‌ند.

# مسیر فایل کش با فرمت JSON (حاوی اطلاعات کامل شامل Slug)
BUSINESS_CACHE_PATH = os.path.join("knowledgebase", "business_cache.json")

class CategoryManager:
    # -----------------------------------------------------------------------
    # متغیرهای حافظه (RAM)
    # -----------------------------------------------------------------------
    # متنی که به System Prompt هوش مصنوعی تزریق می‌شود (فقط شامل ID و نام)
    _categories_text: str = ""
    
    # دیکشنری برای تبدیل سریع ID به Slug در زمان اجرای ابزار
    # مثال: { 1: "تعویض-روغنی", 2: "نانوایی" }
    _id_to_slug_map: dict[int, str] = {} 
    
    _updater_task: Optional[asyncio.Task] = None

    # -----------------------------------------------------------------------
    # چرخه حیات (Lifecycle)
    # -----------------------------------------------------------------------
    @classmethod
    async def start(cls):
        """
        راه‌اندازی سرویس در زمان استارتاپ برنامه.
        """
        # ۱. لود کردن شهرها (از کلاس دیگر)
        CityService.load_cities()
        
        # ۲. تلاش برای لود کردن دیتا از فایل JSON (برای سرعت بالا و حالت آفلاین)
        await cls._load_from_cache()
        
        # ۳. شروع عملیات آپدیت دوره‌ای در پس‌زمینه
        cls._updater_task = asyncio.create_task(cls._updater_loop())
        logger.info("CategoryManager service started.")

    @classmethod
    async def stop(cls):
        """توقف سرویس و آزادسازی منابع"""
        if cls._updater_task:
            cls._updater_task.cancel()
        logger.info("CategoryManager service stopped.")

    # -----------------------------------------------------------------------
    # پردازش و مدیریت داده‌ها (Core Logic)
    # -----------------------------------------------------------------------
    @classmethod
    def _process_data(cls, data_list: list):
        """
        این تابع مغز متفکر است. لیست خام JSON را می‌گیرد و متغیرهای RAM را پر می‌کند.
        """
        # فیلتر کردن آیتم‌های معتبر (باید هم ID داشته باشند، هم Name و هم Slug)
        valid_items = [
            item for item in data_list 
            if isinstance(item, dict) and 'id' in item and 'name' in item and 'slug' in item
        ]
        
        if not valid_items:
            logger.warning("No valid business items found to process.")
            return

        # ۱. ساخت متن برای هوش مصنوعی (فقط چیزهایی که لازم دارد تا گیج نشود)
        # خروجی: "ID: 1 (Name: تعویض روغنی) | ID: 5 (Name: سوپرمارکت)"
        lines = [f"ID: {item['id']} (Name: {item['name']})" for item in valid_items]
        cls._categories_text = " | ".join(lines)

        # ۲. پر کردن دیکشنری ترجمه برای استفاده در tools.py
        # کلید: شناسه عددی | مقدار: اسلاگ متنی برای API
        cls._id_to_slug_map = {item['id']: item['slug'] for item in valid_items}
        
        logger.info(f"Processed {len(valid_items)} businesses into RAM (Prompt + Map).")

    # -----------------------------------------------------------------------
    # عملیات فایل (File I/O)
    # -----------------------------------------------------------------------
    @classmethod
    async def _load_from_cache(cls):
        """خواندن فایل JSON از دیسک و بارگذاری در RAM"""
        try:
            if os.path.exists(BUSINESS_CACHE_PATH):
                async with aiofiles.open(BUSINESS_CACHE_PATH, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                    
                    if not content.strip():
                        return

                    data = json.loads(content) # تبدیل متن فایل به لیست پایتون
                    cls._process_data(data)    # ارسال برای پردازش و پر کردن متغیرها
                    logger.info("Loaded business data from local JSON cache.")
            else:
                logger.warning("No local cache file found. Waiting for API update...")
        except Exception as e:
            logger.error(f"Error reading cache json: {e}")

    @classmethod
    async def _save_to_cache(cls, data: list):
        """ذخیره لیست خام در فایل JSON برای استفاده‌های بعدی"""
        try:
            # اطمینان از وجود پوشه
            os.makedirs(os.path.dirname(BUSINESS_CACHE_PATH), exist_ok=True)
            
            # تبدیل لیست به متن جیسون مرتب شده
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            
            async with aiofiles.open(BUSINESS_CACHE_PATH, mode='w', encoding='utf-8') as f:
                await f.write(json_content)
            logger.info("Updated local JSON cache file.")
        except Exception as e:
            logger.error(f"Error writing cache json: {e}")

    # -----------------------------------------------------------------------
    # عملیات شبکه (Network / API)
    # -----------------------------------------------------------------------
    @classmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def refresh_categories(cls):
        """
        دریافت لیست به‌روز از API بک‌ند.
        """
        client = await get_http_client()
        # اندپوینت دریافت لیست کسب‌وکارها (شامل Slug)
        url = f"{API_BASE_URL}/api/business" 
        
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            
            data = resp.json() # دریافت لیست خام
            
            # گام ۱: اول ذخیره می‌کنیم تا اگر برنامه کرش کرد، دیتا نپرد
            await cls._save_to_cache(data)
            
            # گام ۲: رم را آپدیت می‌کنیم تا تغییرات اعمال شود
            cls._process_data(data)
            
        except Exception as e:
            logger.warning(f"Failed to refresh business list from API: {e}")
            # ارور را Raise نمی‌کنیم، چون دیتای کش شده (فایل) را داریم و برنامه نباید مختل شود.

    @classmethod
    async def _updater_loop(cls):
        """حلقه بی‌نهایت آپدیت در پس‌زمینه"""
        # یک بار بلافاصله آپدیت کن
        await cls.refresh_categories()
        
        while True:
            await asyncio.sleep(CATEGORY_REFRESH_INTERVAL)
            try:
                await cls.refresh_categories()
            except Exception:
                pass 

    # -----------------------------------------------------------------------
    # متدهای عمومی (Public Accessors)
    # -----------------------------------------------------------------------
    @classmethod
    def get_prompt_text(cls) -> str:
        """برای استفاده در chat.py (ساخت پرامپت)"""
        return cls._categories_text or "No services available yet."

    @classmethod
    def get_slug_by_id(cls, category_id: int) -> Optional[str]:
        """برای استفاده در tools.py (تبدیل ID هوش مصنوعی به Slug بک‌ند)"""
        return cls._id_to_slug_map.get(category_id)


# --------------------------------------------------------------------------- #
# بخش ۴: سرویس موقعیت‌یابی (GeoService) با رعایت محدودیت‌ها
# --------------------------------------------------------------------------- #
# چالش‌ها:
# ۱. Nominatim محدودیت ۱ درخواست در ثانیه دارد (Rate Limit).
# ۲. کتابخانه geopy همگام (Sync) است و سرور را قفل می‌کند.
# ۳. Thread Safety در محیط‌های همزمان.

# class GeoService:
#     # نمونه ثابت Nominatim برای استفاده مجدد (بهینه‌سازی منابع)
#     _geolocator = Nominatim(user_agent="persian_bot_agent_v1", timeout=5)
    
#     # قفل برای کنترل دسترسی همزمان (Rate Limiting Queue)
#     _lock = asyncio.Lock()
    
#     # زمان آخرین درخواست موفق
#     _last_call_time: float = 0
    
#     # حداقل فاصله زمانی بین درخواست‌ها (۱.۱ ثانیه برای اطمینان)
#     _MIN_INTERVAL: float = 1.1

#     @classmethod
#     async def get_city_from_coords(cls, lat: float, lon: float) -> Optional[str]:
#         """
#         تبدیل مختصات به نام شهر (Reverse Geocoding).
#         """
#         try:
#             # استفاده از Lock: درخواست‌ها به صف می‌شوند و یکی‌یکی وارد بلوک زیر می‌شوند
#             async with cls._lock:
                
#                 # ۱. بررسی زمان گذشته از آخرین درخواست
#                 now = time.time()
#                 elapsed = now - cls._last_call_time
                
#                 # ۲. اگر کمتر از ۱.۱ ثانیه گذشته بود، صبر کن
#                 if elapsed < cls._MIN_INTERVAL:
#                     wait_time = cls._MIN_INTERVAL - elapsed
#                     logger.debug(f"GeoService Rate Limit: Sleeping {wait_time:.2f}s")
#                     await asyncio.sleep(wait_time)
                
#                 # ۳. اجرای عملیات سنگین در ترد جداگانه (Non-blocking)
#                 loop = asyncio.get_running_loop()
                
#                 def _sync_geo():
#                     return cls._geolocator.reverse((lat, lon), language='fa', exactly_one=True)

#                 location = await loop.run_in_executor(None, _sync_geo)
                
#                 # ۴. ثبت زمان اجرا
#                 cls._last_call_time = time.time()
            
#             # ۵. پردازش نتیجه
#             if location and location.raw and 'address' in location.raw:
#                 address = location.raw['address']
#                 # جستجو در فیلدهای مختلف آدرس
#                 city = (
#                     address.get('city') or 
#                     address.get('town') or 
#                     address.get('village') or 
#                     address.get('county')
#                 )
#                 if city:
#                     # حذف کلمات اضافی مثل "شهرستان"
#                     return city.replace("شهرستان", "").replace("شهر", "").strip()
            
#             return None
            
#         except GeocoderTimedOut:
#             logger.warning("GeoService timed out.")
#             return None
#         except GeocoderServiceError as e:
#             logger.error(f"GeoService API error: {e}")
#             return None
#         except Exception as e:
#             logger.error(f"Unexpected GeoService error: {e}", exc_info=True)
#             return None



# --------------------------------------------------------------------------- #
# بخش ۲: توابع کمکی (Helper Functions)
# --------------------------------------------------------------------------- #

@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
async def _call_backend_api(params: dict) -> httpx.Response:
    """
    ارسال درخواست جستجو به بک‌ند دات‌نت با قابلیت تلاش مجدد خودکار.
    """
    # دریافت کلاینت اشتراکی از سرویس‌ها
    client = await get_http_client()
    
    # آدرس اندپوینت جستجو
    url = f"{API_BASE_URL}/api/booths"
    
    # ارسال درخواست GET
    return await client.get(url, params=params)