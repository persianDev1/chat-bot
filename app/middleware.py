# app/middleware.py

import time
import redis
import logging
import uuid
from fastapi.responses import JSONResponse
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

# Import request_id_var from logging_config
from .logging_config import request_id_var

# یک لاگر برای این ماژول می‌گیریم تا از سیستم لاگینگ مرکزی استفاده کنیم
logger = logging.getLogger("app." + __name__)

# --------------------------------------------------------------------------- #
# Middleware شماره ۱: مدیریت خطاهای عمومی (بیرونی‌ترین لایه)
# --------------------------------------------------------------------------- #
class GlobalErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    یک Middleware برای مدیریت خطاهای پیش‌بینی نشده در سطح کل برنامه.
    این Middleware باید اولین لایه (بیرونی‌ترین) باشد تا بتواند خطاهای
    لایه‌های داخلی‌تر را نیز مدیریت کند.
    """
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        try:
            # تلاش برای اجرای بقیه Middleware ها و Endpoint
            response = await call_next(request)
            return response
        except HTTPException as exc:
            # اگر خطا از نوع HTTPException بود (خطای کنترل شده)، اجازه می‌دهیم
            # FastAPI به صورت عادی آن را مدیریت کند.
            raise exc
        except Exception as exc:
            # اگر هر نوع خطای پیش‌بینی نشده دیگری رخ داد
            logger.error(f"خطای پیش‌بینی نشده در مسیر {request.url.path}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "یک خطای داخلی در سرور رخ داده است."}
            )



# --------------------------------------------------------------------------- #
# یک لاگر حرفه ای
# شماره 2 : اضافه کردین request id به لاگ ها و time و اطلاعات شی درخواست مانند method و url و ...
# --------------------------------------------------------------------------- #
class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # مرحله ۱ و ۲: ساخت شناسه یکتا و قرار دادن در ContextVar
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)

        # مرحله ۳ و ۴: ثبت زمان شروع و لاگ اولیه
        start_time = time.time()
        logger.info(f"Request started: {request.method} {request.url.path}")

        try:
            # مرحله ۵: ارسال درخواست به لایه‌های داخلی
            response = await call_next(request)
        finally:
            # مرحله ۶: محاسبه زمان کل پردازش
            process_time = time.time() - start_time
            
            # مرحله ۷ (که قبلاً در Middleware دیگری بود): اضافه کردن هدر به پاسخ
            # چون response ممکن است در صورت بروز خطا ساخته نشود، این کار را در بلوک finally انجام نمی‌دهیم
            # و به بعد از آن منتقل می‌کنیم.

        # مرحله ۷ و ۸: اضافه کردن هدر و ثبت لاگ نهایی
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        logger.info(
            f"Request finished: {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {process_time:.4f}s"
        )
        
        # مرحله ۹: پاکسازی ContextVar
        request_id_var.reset(token)
        
        return response



# --------------------------------------------------------------------------- #
# Middleware شماره ۳: محدود کننده نرخ (Rate Limiter)
# --------------------------------------------------------------------------- #

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    یک Middleware برای محدود کردن تعداد درخواست‌های هر IP (Rate Limiting).
    این Middleware از Redis برای ذخیره وضعیت به صورت مرکزی استفاده می‌کند تا در محیط‌های
    چند-پردازشی (multi-process) به درستی کار کند.
    """
    def __init__(
        self, 
        app, 
        requests_per_hour: int, 
        redis_client: redis.Redis
    ):
        """
        سازنده Middleware.

        Args:
            app: اپلیکیشن FastAPI.
            requests_per_hour (int): حداکثر تعداد درخواست مجاز در ساعت برای هر IP.
            redis_client (redis.Redis): یک کلاینت متصل به سرور Redis.
        """
        super().__init__(app)
        self.requests_per_hour = requests_per_hour
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next):
        """
        متد اصلی که برای هر درخواست اجرا می‌شود.
        """
        # اگر مسیر درخواست مربوط به فایل‌های استاتیک یا داکیومنت‌ها بود، آن را نادیده بگیر
        if request.url.path.startswith("/static") or request.url.path.startswith("/docs"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # یک کلید یکتا برای هر IP در Redis می‌سازیم
        redis_key = f"rate_limit:{client_ip}"
        one_hour_ago = current_time - 3600  # 3600 ثانیه = 1 ساعت

        try:
            # استفاده از Pipeline برای اجرای بهینه و یکجای دستورات Redis
            pipe = self.redis.pipeline()
            
            # ۱. حذف تمام رکوردهای قدیمی‌تر از یک ساعت قبل
            pipe.zremrangebyscore(redis_key, 0, one_hour_ago)
            
            # ۲. شمارش تعداد رکوردهای باقی‌مانده (درخواست‌های اخیر)
            pipe.zcard(redis_key)
            
            # ۳. ثبت زمان درخواست فعلی
            pipe.zadd(redis_key, {str(current_time): current_time})
            
            # ۴. تنظیم زمان انقضا برای کلید جهت صرفه‌جویی در حافظه
            pipe.expire(redis_key, 3600)
            
            # اجرای تمام دستورات
            results = pipe.execute()
            
            # نتیجه دستور دوم (zcard)، تعداد درخواست‌های اخیر است
            request_count = results[1]
            
            # ۵. اعمال قانون: اگر تعداد درخواست‌ها از حد مجاز بیشتر بود، خطا برگردان
            if request_count > self.requests_per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"تعداد درخواست‌ها از حد مجاز ({self.requests_per_hour} در ساعت) فراتر رفته است."
                )
        except redis.RedisError:
            # اگر Redis در دسترس نبود، اجازه دهید درخواست ادامه پیدا کند (بدون محدودیت نرخ)
            logger.warning("Redis is not available. Rate limiting is disabled.")
        except Exception as e:
            # اگر خطای دیگری رخ داد، اجازه دهید درخواست ادامه پیدا کند
            logger.error(f"Error in rate limiting: {e}")

        # اگر محدودیتی وجود نداشت، درخواست را به مرحله بعد بفرست
        response = await call_next(request)
        return response