# app/logging_config.py
import logging
import logging.config
import os

from contextvars import ContextVar

# یک ContextVar برای نگهداری Request ID در طول یک درخواست می سازیم
request_id_var: ContextVar[str] = ContextVar("request_id", default="N/A")


# یک فیلتر سفارشی برای تزریق Request ID به رکوردهای لاگ می سازیم
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True




# --------------------------------------------------------------------------- #
# بخش ۲: دیکشنری تنظیمات لاگینگ (نقشه کامل سیستم)
# --------------------------------------------------------------------------- #
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    # تعریف فیلتر سفارشی برای استفاده در هندلرها
    "filters": {
        "request_id": {
            "()": RequestIdFilter,
        },
    },
    # تعریف قالب‌های نمایش پیام
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(request_id)s - %(name)s - %(levelname)s - %(message)s",
        },
        "simple": {
            "format": "%(levelname)s: [%(request_id)s] %(message)s",
        },
    },
    # تعریف مقصدها (دکل‌های مخابراتی)
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "INFO",
            "filters": ["request_id"], # اعمال فیلتر
        },
        "file_app": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": "logs/app.log",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "level": "DEBUG",
            "filters": ["request_id"], # اعمال فیلتر
        },
        "file_db": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": "logs/db.log",
            "maxBytes": 1024 * 1024 * 2,  # 2 MB
            "backupCount": 5,
            "level": "DEBUG",
            "filters": ["request_id"], # اعمال فیلتر
        },
        "file_openai": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": "logs/openai.log",
            "maxBytes": 1024 * 1024 * 2,  # 2 MB
            "backupCount": 5,
            "level": "DEBUG",
            "filters": ["request_id"], # اعمال فیلتر
        },
    },
    # پیکربندی ایستگاه‌های رادیویی
    "loggers": {
        "app": {
            "handlers": ["console", "file_app"],
            "level": "DEBUG",
            "propagate": False,
        },
        "db": {
            "handlers": ["console", "file_db"],
            "level": "DEBUG",
            "propagate": False,
        },
        "openai": {
            "handlers": ["console", "file_openai"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
    # پیکربندی لاگر ریشه
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}
# --------------------------------------------------------------------------- #
# بخش ۲: توابع کمکی و راه‌اندازی
# --------------------------------------------------------------------------- #

def setup_logging():
    """
    سیستم لاگینگ را بر اساس دیکشنری بالا راه‌اندازی می‌کند.
    """
    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)

def log_before_retry(retry_state):
    """
    یک تابع callback برای کتابخانه Tenacity.
    قبل از هر تلاش مجدد برای یک تابع، یک پیام هشدار لاگ می‌کند.
    """
    # لاگر مخصوص کانال 'openai' را دریافت می‌کنیم
    logger = logging.getLogger("openai")
    
    # اطلاعات مفیدی از وضعیت تلاش مجدد را استخراج می‌کنیم
    attempt_number = retry_state.attempt_number
    wait_time = retry_state.next_action.sleep
    
    # پیام هشدار را لاگ می‌کنیم
    logger.warning(
        f"تلاش مجدد برای فراخوانی API... تلاش شماره: {attempt_number}, "
        f"زمان انتظار قبل از تلاش بعدی: {wait_time:.2f} ثانیه"
    )