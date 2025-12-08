import json
from thefuzz import process

# تنظیمات
JSON_PATH = 'cities.json'
TARGET_PROVINCE_ID = 4  # فقط استان اصفهان

def load_isfahan_map():
    """
    این تابع جیسون را می‌خواند و یک 'دیکشنری' می‌سازد.
    کلید: اسم شهر (مثلاً 'نجف آباد')
    مقدار: آی‌دی شهر (مثلاً 188)
    فقط هم شهرهای اصفهان را برمی‌دارد.
    """
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # فیلتر کردن و ساخت مپ
        # city_map = { "نجف آباد": 188, "کاشان": 143, ... }
        city_map = {}
        
        for city in data['cities']:
            if city['provinceId'] == TARGET_PROVINCE_ID:
                city_name = city['name']
                city_id = city['id']
                city_map[city_name] = city_id
                
        return city_map
        
    except FileNotFoundError:
        print("❌ فایل جیسون پیدا نشد.")
        return {}

def find_city_id(user_input, city_map):
    """
    ورودی: متنی که کاربر نوشته (مثلاً 'شهرستان نجف اباد')
    خروجی: آی‌دی پیدا شده (مثلاً 188)
    """
    if not user_input or not city_map:
        return None

    # 1. تمیزکاری اولیه (پاک کردن کلمات اضافه)
    clean_input = user_input.replace("شهرستان", "").replace("شهر", "").strip()
    # تبدیل ی و ک عربی به فارسی
    clean_input = clean_input.replace("ي", "ی").replace("ك", "ک")

    # 2. لیست تمام اسم‌های صحیح موجود در دیتابیس
    valid_names = list(city_map.keys())

    # 3. استفاده از extractOne برای پیدا کردن بهترین شباهت
    # این تابع، clean_input را با تک تک valid_names مقایسه می‌کند
    # و شبیه‌ترین گزینه را برمی‌گرداند.
    match_result = process.extractOne(clean_input, valid_names)
    
    if match_result:
        best_match_name = match_result[0] # نام شهر پیدا شده (مثلاً "نجف آباد")
        score = match_result[1]           # امتیاز شباهت (0 تا 100)
        
        # لاگ آموزشی برای اینکه ببینی چی شد
        print(f"   🔍 ورودی: '{user_input}' -> تمیزشده: '{clean_input}'")
        print(f"   🎯 بهترین حدس: '{best_match_name}' با امتیاز {score}%")

        # اگر شباهت بالای 85 درصد بود، قبول می‌کنیم
        if score >= 85:
            found_id = city_map[best_match_name]
            return found_id
        else:
            print("   ⚠️ امتیاز شباهت پایین بود (ریسک خطا).")
            
    return None

# --- اجرای تست ---
if __name__ == "__main__":
    print("--- 📥 در حال بارگذاری شهرهای اصفهان... ---")
    cities_map = load_isfahan_map()
    print(f"✅ تعداد {len(cities_map)} شهر بارگذاری شد.\n")

    # لیست تست‌هایی که می‌خواهیم انجام دهیم
    test_inputs = [
        "نجف آباد",          # دقیق
        "نجف اباد",          # بدون آ
        "شهرستان نجف آباد",  # با پیشوند
        "شاهین شهر",         # دقیق
        "شاهینشهر",          # چسبیده
        "کاشان",             # دقیق
        "تهران",             # شهر خارج از استان (نباید پیدا شود یا امتیاز کم بگیرد)
        "اصفهان",            # مرکز استان
        "سمیرم"
    ]

    for text in test_inputs:
        print(f"🔸 تست برای: [{text}]")
        result_id = find_city_id(text, cities_map)
        
        if result_id:
            print(f"✅ نتیجه نهایی: ID = {result_id}")
        else:
            print("❌ نتیجه: پیدا نشد.")
        print("-" * 40)