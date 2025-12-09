# app/main.py ────────────────────────────────────────────────────────────

import os
import logging
import asyncio
from contextlib import asynccontextmanager

# کتابخانه‌های اصلی FastAPI
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .services import CategoryManager

# کتابخانه Redis (نسخه Async)
import redis.asyncio as redis_async

# ماژول‌های داخلی پروژه
from .middleware import (
    GlobalErrorHandlerMiddleware, 
    AccessLogMiddleware, 
    RateLimitMiddleware
)
from .routers.chat import router
from .logging_config import setup_logging

# --------------------------------------------------------------------------- #
# بخش ۱: تنظیمات اولیه و لاگینگ
# --------------------------------------------------------------------------- #
load_dotenv()
setup_logging()
app_logger = logging.getLogger("app." + __name__)

# --------------------------------------------------------------------------- #
# بخش ۲: اتصال به Redis (با مدیریت خطا)
# --------------------------------------------------------------------------- #
redis_url = os.getenv("REDIS_URL")
redis_client = None

try:
    if redis_url:
        # حالت ۱: اتصال از طریق URL (معمولاً در سرور واقعی/Docker)
        redis_client = redis_async.from_url(redis_url, encoding="utf-8", decode_responses=True)
        app_logger.info(f"✅ Redis connected via URL: {redis_url}")
    else:
        # حالت ۲: تلاش برای اتصال به لوکال هاست پیش‌فرض
        # اگر نمی‌خواهید روی سیستم خودتان به ردیس وصل شوید، این قسمت try را کلاً حذف کنید و redis_client = None بگذارید
        redis_client = redis_async.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        # یک تست اتصال سریع (Ping)
        # نکته: چون اینجا هنوز در Loop نیستیم، پینگ نمی‌گیریم، فقط کلاینت را می‌سازیم.
        # اتصال واقعی زمانی رخ می‌دهد که اولین درخواست بیاید.
        app_logger.info("⚠️ No REDIS_URL found. Trying localhost default.")

except Exception as e:
    app_logger.warning(f"⚠️ Redis connection failed. Rate limiting will be disabled. Error: {e}")
    redis_client = None

# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# بخش : مدیریت چرخه حیات (Lifespan) - 
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP (روشن شدن) ---
    app_logger.info("🚀 Application is starting up...")
    
    # استارت سرویس دسته‌بندی‌ها (خواندن فایل و آپدیت از API)
    await CategoryManager.start()
    
    yield # اینجا برنامه اجرا می‌شود
    
    # --- SHUTDOWN (خاموش شدن) ---
    app_logger.info("🛑 Application is shutting down...")
    
    # توقف سرویس‌ها
    await CategoryManager.stop()
    
    # بستن ردیس
    if redis_client:
        await redis_client.aclose()
# --------------------------------------------------------------------------- #
# بخش ۳: ساخت اپلیکیشن FastAPI
# --------------------------------------------------------------------------- #
app = FastAPI(title="Persian Chatbot", lifespan=lifespan)

# سرو کردن فایل‌های استاتیک (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# مسیر صفحه اصلی
@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

# اضافه کردن روتر چت
app.include_router(router)

# --------------------------------------------------------------------------- #
# بخش ۴: نصب Middleware ها (ترتیب بسیار مهم است)
# --------------------------------------------------------------------------- #

# ۱. مدیریت خطا (بیرونی‌ترین لایه - باید همه چیز را پوشش دهد)
app.add_middleware(GlobalErrorHandlerMiddleware)

# ۲. لاگینگ (باید قبل از تغییر هدرها اجرا شود)
app.add_middleware(AccessLogMiddleware)

# ۳. مدیریت CORS (برای امنیت مرورگر)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # در پروداکشن حتماً به دامین خود محدود کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ۴. محدودیت نرخ (درونی‌ترین لایه - نزدیک‌ترین به لاجیک برنامه)
app.add_middleware(
    RateLimitMiddleware, 
    redis_client=redis_client,
    requests_per_hour=25
)

# --------------------------------------------------------------------------- #
# بخش ۵: اجرا (فقط برای تست دستی)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)