# app/schemas.py

from pydantic import BaseModel, Field

# مدل ورودی برای اندپوینت /start_chat که شماره تلفن را اعتبارسنجی می‌کند
class StartChatRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^09\d{9}$')

# مدل ورودی برای اندپوینت /chat که شناسه گفتگو و پیام را اعتبارسنجی می‌کند
class ChatRequest(BaseModel):
    conversation_id: str = Field(..., pattern=r'^09\d{9}$')
    message: str = Field(..., min_length=1, max_length=5000)