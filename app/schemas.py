# app/schemas.py
from typing import Optional  
from pydantic import BaseModel, Field, model_validator

# مدل ورودی برای اندپوینت /start_chat که شماره تلفن را اعتبارسنجی می‌کند
class StartChatRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^09\d{9}$')

# مدل ورودی برای اندپوینت /chat که شناسه گفتگو و پیام را اعتبارسنجی می‌کند

class ChatRequest(BaseModel):
    # شناسه گفتگو (همان شماره موبایل)
    conversation_id: str = Field(..., pattern=r'^09\d{9}$')
    
    # متن پیام کاربر (حداقل 1 کاراکتر)
    message: str = Field(..., min_length=1, max_length=500)
    
    # عرض جغرافیایی (Latitude) - اختیاری
    # مثال: 35.6892 (تهران)
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="User's latitude")
    
    # طول جغرافیایی (Longitude) - اختیاری
    # مثال: 51.3890 (تهران)
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="User's longitude")
    
    #نام شهر کاربر که فرانت‌‌اند از روی لوکیشن او تشخیص داده
    client_city_name: Optional[str] = Field(None, description="The user's city name, which the frontend recognized from their location.")
    
    
    
    # ✅ اعتبارسنجی ترکیبی (Cross-field Validation)
    @model_validator(mode='after')
    def validate_coordinates(self):
        lat = self.latitude
        lon = self.longitude
        
        # منطق XOR: یا هر دو باید باشند، یا هیچکدام
        # اگر یکی باشد و دیگری نباشد، خطا تولید می‌کنیم
        if (lat is None) != (lon is None):
            raise ValueError("مختصات جغرافیایی ناقص است. هم Latitude و هم Longitude باید با هم ارسال شوند (یا هیچکدام).")
        
        return self