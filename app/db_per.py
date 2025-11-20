# استفاده از sqlite3 فقط برای کلاس‌های خطا
import sqlite3
import aiosqlite
from typing import List, Dict
import logging

# Timeout (in seconds) برای جلوگیری از انتظار طولانی در صورت قفل‌شدن دیتابیس
DB_TIMEOUT_SECONDS = 30


logger = logging.getLogger("db." + __name__)
# connection = sqlite3.connect('ai.db') 
# cursor = connection.cursor()

# دستور SQL برای ساخت جدول
# CREATE_MESSAGES_TABLE_QUERY = """
# CREATE TABLE IF NOT EXISTS messages (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     conversation_id TEXT NOT NULL,
#     role TEXT NOT NULL,
#     content TEXT NOT NULL,
#     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# );
# """

# cursor.execute(CREATE_MESSAGES_TABLE_QUERY)
# connection.commit() 

#lets index bro:


DB_NAME = 'ai.db' 
# CREATE_INDEX_QUERY = """
# CREATE INDEX IF NOT EXISTS idx_messages_conv_time 
# ON messages (conversation_id, timestamp);
# """

# cursor.execute(CREATE_INDEX_QUERY)
# connection.commit() 
# connection.close()


# print(f"در حال بررسی ایندکس‌های موجود در دیتابیس '{DB_NAME}'...")

# try:
#     with sqlite3.connect(DB_NAME) as conn:
#         cursor = conn.cursor()
        
#         # این کوئری تمام ایندکس‌ها را از جدول مستر SQLite لیست می‌کند
#         query = "SELECT name FROM sqlite_master WHERE type='index';"
#         cursor.execute(query)
        
#         indexes = cursor.fetchall()
        
#         if not indexes:
#             print("هیچ ایندکستی در این دیتابیس پیدا نشد.")
#         else:
#             print("ایندکس‌های پیدا شده:")
#             found = False
#             for index in indexes:
#                 print(f"- {index[0]}")
#                 if index[0] == 'idx_messages_conv_time':
#                     found = True
            
#             if found:
#                 print("\n✅ تایید شد! ایندکس 'idx_messages_conv_time' با موفقیت وجود دارد.")
#             else:
#                 print("\n❌ هشدار: ایندکس مورد نظر شما پیدا نشد.")

# except sqlite3.Error as e:
#     print(f"یک خطای دیتابیس رخ داد: {e}")



async def get_last_20_messages(conversation_id: str) -> List[Dict]:
    """
    آخرین ۲۰ پیام یک گفتگوی خاص را از دیتابیس خوانده و
    در فرمت مناسب برای مدل OpenAI برمی‌گرداند.
    """
    logger.debug(f"در حال خواندن تاریخچه برای {conversation_id}")
    query = """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY timestamp DESC
        LIMIT 20;
    """

    try:
        async with aiosqlite.connect(DB_NAME, timeout=DB_TIMEOUT_SECONDS) as conn:
            # فعال کردن WAL برای بهبود خواندن/نوشتن هم‌زمان
            await conn.execute("PRAGMA journal_mode=WAL;")

            cursor = await conn.execute(query, (conversation_id,))
            results_newest_to_oldest = await cursor.fetchall()
            await cursor.close()

        history_oldest_to_newest = list(reversed(results_newest_to_oldest))
        logger.info(f"تعداد {len(history_oldest_to_newest)} پیام برای {conversation_id} پیدا شد.")
        messages_for_model = [{"role": role, "content": content} for role, content in history_oldest_to_newest]
        return messages_for_model

    except sqlite3.Error as e:
        logger.error("خطا در خواندن تاریخچه", exc_info=True)
        return [] # در صورت خطا، یک لیست خالی برگردان

# --- مثال برای تست تابع ---
# if __name__ == "__main__":
#     # فرض کنید می‌خواهیم تاریخچه کاربر '09121112233' را بگیریم
#     # (این کاربر را در مثال‌های قبلی به دیتابیس اضافه کردیم)
#     test_conversation_id = '09123456789' 
#     history = get_last_20_messages(test_conversation_id)
    
#     print(f"تاریخچه برای کاربر {test_conversation_id}:")
#     for message in history:
#         print(f"- {message['role']}: {message['content']}")




async def save_message(conversation_id: str, role: str, content: str):
    """
    Saves a new message to the 'messages' table in the database.

    Args:
        conversation_id: The identifier for the conversation (e.g., user's phone number).
        role: The role of the speaker ('user' or 'assistant').
        content: The text content of the message.
    """
    logger.debug(f"تلاش برای ذخیره پیام از '{role}' برای کاربر '{conversation_id}'")

    query = "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?);"
    data_to_insert = (conversation_id, role, content)

    try:
        async with aiosqlite.connect(DB_NAME, timeout=DB_TIMEOUT_SECONDS) as conn:
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute(query, data_to_insert)
            await conn.commit()
        logger.info("پیام با موفقیت در دیتابیس ذخیره شد.")
    except sqlite3.Error as e:
        logger.error("خطا هنگام ذخیره پیام در دیتابیس", exc_info=True)

# --- Test block for the function (to run this file directly) ---
# if __name__ == "__main__":
#     print("--- Testing save_message function ---")
    
#     # A test conversation ID
#     test_id = '09121234567'
    
#     # Save a message from the user
#     save_message(test_id, 'user', 'This is my first test message to be saved.')
    
#     # Save a response from the assistant
#     save_message(test_id, 'assistant', "And this is the assistant's response for the test.")
    
#     print("\n--- Verifying saved data in the database ---")
#     try:
#         with sqlite3.connect(DB_NAME) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT * FROM messages WHERE conversation_id = ?", (test_id,))
#             saved_rows = cursor.fetchall()
            
#             print(f"Messages found for conversation {test_id}:")
#             for row in saved_rows:
#                 print(row)
#     except sqlite3.Error as e:
#         print(f"Error while reading test data: {e}")



# Add this function to your database utility file

async def user_exists(conversation_id: str) -> bool:
    """
    Checks if at least one message exists for a given conversation_id in the database.
    """
    logger.debug(f"در حال بررسی وجود کاربر {conversation_id}")
    query = "SELECT 1 FROM messages WHERE conversation_id = ? LIMIT 1;"
    try:
        async with aiosqlite.connect(DB_NAME, timeout=DB_TIMEOUT_SECONDS) as conn:
            await conn.execute("PRAGMA journal_mode=WAL;")
            cursor = await conn.execute(query, (conversation_id,))
            result = await cursor.fetchone()
            await cursor.close()
            exists = result is not None
            logger.info(f"نتیجه بررسی وجود کاربر {conversation_id}: {exists}")
            return exists
    except sqlite3.Error as e:
        logger.error("خطا هنگام بررسی وجود کاربر", exc_info=True)
        return False
    
    
    
    
    
    
def load_prompt_from_file(file_path: str) -> str:
    try:
        logger.debug(f"در حال بارگذاری پرامپت از مسیر {file_path}")
        # 'utf-8' is necessary for supporting Persian
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"فایل پرامپت در مسیر {file_path} یافت نشد.", exc_info=True)