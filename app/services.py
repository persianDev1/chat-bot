# app/services.py ────────────────────────────────────────────────────────────

import logging
import asyncio
import os
import time
from typing import Optional

# کتابخانه‌های شبکه و فایل
import httpx
import aiofiles

# کتابخانه‌های موقعیت‌یابی
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

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
# بخش ۳: سرویس مدیریت دسته‌بندی‌ها (Category Manager)
# --------------------------------------------------------------------------- #
# وظایف:
# ۱. کش کردن لیست شغل‌ها در حافظه و فایل.
# ۲. آپدیت خودکار در پس‌زمینه.
# ۳. ارائه لیست فرمت‌دهی شده برای پرامپت هوش مصنوعی.

class CategoryManager:
    _categories_text: str = ""
    _updater_task: Optional[asyncio.Task] = None

    @classmethod
    async def start(cls):
        """
        متد راه‌اندازی سرویس (در Startup اجرا می‌شود).
        """
        # ۱. تلاش برای خواندن از فایل (سریع‌ترین روش برای بالا آمدن برنامه)
        await cls._load_from_file()
        
        # ۲. شروع تسک آپدیت در پس‌زمینه (بدون بلاک کردن برنامه اصلی)
        cls._updater_task = asyncio.create_task(cls._updater_loop())
        logger.info("CategoryManager service started.")

    @classmethod
    async def stop(cls):
        """
        متد توقف سرویس (در Shutdown اجرا می‌شود).
        """
        if cls._updater_task:
            cls._updater_task.cancel()
        logger.info("CategoryManager service stopped.")

    @classmethod
    async def _load_from_file(cls):
        """
        خواندن اطلاعات از فایل کش (Fallback Mechanism).
        """
        try:
            if os.path.exists(CATEGORIES_FILE_PATH):
                async with aiofiles.open(CATEGORIES_FILE_PATH, mode='r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        cls._categories_text = content
                        logger.info("Loaded categories from local cache file.")
            else:
                logger.warning("No local cache file found.")
        except Exception as e:
            logger.error(f"Error reading cache file: {e}")

    @classmethod
    async def _save_to_file(cls, content: str):
        """
        ذخیره اطلاعات جدید در فایل.
        """
        try:
            os.makedirs(os.path.dirname(CATEGORIES_FILE_PATH), exist_ok=True)
            async with aiofiles.open(CATEGORIES_FILE_PATH, mode='w', encoding='utf-8') as f:
                await f.write(content)
            logger.info("Updated local cache file.")
        except Exception as e:
            logger.error(f"Error writing to cache file: {e}")

    @classmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def refresh_categories(cls):
        """
        دریافت لیست تازه از API و آپدیت کردن کش.
        دارای مکانیزم Retry خودکار در صورت خطای شبکه.
        """
        client = await get_http_client()
        url = f"{API_BASE_URL}/api/business-category"
        
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            
            data = resp.json()
            # اعتبارسنجی ساده داده‌ها
            valid_items = [
                item for item in data 
                if isinstance(item, dict) and 'id' in item and 'name' in item
            ]

            if not valid_items:
                return

            # فرمت‌دهی متن: "ID: 1 (Name: نانوایی) | ..."
            lines = [f"ID: {item['id']} (Name: {item['name']})" for item in valid_items]
            new_text = " | ".join(lines)
            
            # فقط اگر دیتا تغییر کرده بود ذخیره کن (بهینه‌سازی I/O)
            if new_text != cls._categories_text:
                cls._categories_text = new_text
                await cls._save_to_file(new_text)
                logger.info(f"Categories refreshed from API. Count: {len(valid_items)}")
            
        except Exception as e:
            logger.warning(f"Failed to refresh categories from API (using cache): {e}")

    @classmethod
    async def _updater_loop(cls):
        """حلقه بی‌نهایت برای آپدیت دوره‌ای"""
        # آپدیت اولیه
        await cls.refresh_categories()
        
        while True:
            await asyncio.sleep(CATEGORY_REFRESH_INTERVAL)
            try:
                await cls.refresh_categories()
            except Exception:
                pass # خطاها قبلاً هندل شده‌اند

    @classmethod
    def get_prompt_text(cls) -> str:
        """دسترسی عمومی به متن آماده"""
        return cls._categories_text or "No categories available yet."


# --------------------------------------------------------------------------- #
# بخش ۴: سرویس موقعیت‌یابی (GeoService) با رعایت محدودیت‌ها
# --------------------------------------------------------------------------- #
# چالش‌ها:
# ۱. Nominatim محدودیت ۱ درخواست در ثانیه دارد (Rate Limit).
# ۲. کتابخانه geopy همگام (Sync) است و سرور را قفل می‌کند.
# ۳. Thread Safety در محیط‌های همزمان.

class GeoService:
    # نمونه ثابت Nominatim برای استفاده مجدد (بهینه‌سازی منابع)
    _geolocator = Nominatim(user_agent="persian_bot_agent_v1", timeout=5)
    
    # قفل برای کنترل دسترسی همزمان (Rate Limiting Queue)
    _lock = asyncio.Lock()
    
    # زمان آخرین درخواست موفق
    _last_call_time: float = 0
    
    # حداقل فاصله زمانی بین درخواست‌ها (۱.۱ ثانیه برای اطمینان)
    _MIN_INTERVAL: float = 1.1

    @classmethod
    async def get_city_from_coords(cls, lat: float, lon: float) -> Optional[str]:
        """
        تبدیل مختصات به نام شهر (Reverse Geocoding).
        """
        try:
            # استفاده از Lock: درخواست‌ها به صف می‌شوند و یکی‌یکی وارد بلوک زیر می‌شوند
            async with cls._lock:
                
                # ۱. بررسی زمان گذشته از آخرین درخواست
                now = time.time()
                elapsed = now - cls._last_call_time
                
                # ۲. اگر کمتر از ۱.۱ ثانیه گذشته بود، صبر کن
                if elapsed < cls._MIN_INTERVAL:
                    wait_time = cls._MIN_INTERVAL - elapsed
                    logger.debug(f"GeoService Rate Limit: Sleeping {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                
                # ۳. اجرای عملیات سنگین در ترد جداگانه (Non-blocking)
                loop = asyncio.get_running_loop()
                
                def _sync_geo():
                    return cls._geolocator.reverse((lat, lon), language='fa', exactly_one=True)

                location = await loop.run_in_executor(None, _sync_geo)
                
                # ۴. ثبت زمان اجرا
                cls._last_call_time = time.time()
            
            # ۵. پردازش نتیجه
            if location and location.raw and 'address' in location.raw:
                address = location.raw['address']
                # جستجو در فیلدهای مختلف آدرس
                city = (
                    address.get('city') or 
                    address.get('town') or 
                    address.get('village') or 
                    address.get('county')
                )
                if city:
                    # حذف کلمات اضافی مثل "شهرستان"
                    return city.replace("شهرستان", "").replace("شهر", "").strip()
            
            return None
            
        except GeocoderTimedOut:
            logger.warning("GeoService timed out.")
            return None
        except GeocoderServiceError as e:
            logger.error(f"GeoService API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected GeoService error: {e}", exc_info=True)
            return None