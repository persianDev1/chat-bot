# app/schemas.py

from pydantic import BaseModel, Field

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