// ========================================
// تنظیمات و متغیرهای سراسری
// ========================================
const API_BASE_URL = 'http://127.0.0.1:8000';
let conversationId = null;

// ========================================
// عناصر DOM
// ========================================
const elements = {
    loginPage: document.getElementById('login-page'),
    chatPage: document.getElementById('chat-page'),
    phoneInput: document.getElementById('phone-input'),
    phoneError: document.getElementById('phone-error'),
    startChatBtn: document.getElementById('start-chat-btn'),
    chatMessages: document.getElementById('chat-messages'),
    messageForm: document.getElementById('message-form'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    backBtn: document.getElementById('back-btn'),
    clearChatBtn: document.getElementById('clear-chat-btn'),
    typingIndicator: document.getElementById('typing-indicator'),
    notification: document.getElementById('notification')
};

// ========================================
// مدیریت LocalStorage
// ========================================

/**
 * کلید برای ذخیره تاریخچه چت‌ها
 */
function getChatHistoryKey(phoneNumber) {
    return `chat_history_${phoneNumber}`;
}

/**
 * ذخیره پیام در LocalStorage
 */
function saveMessageToLocalStorage(phoneNumber, role, content) {
    try {
        const key = getChatHistoryKey(phoneNumber);
        let history = JSON.parse(localStorage.getItem(key) || '[]');
        
        history.push({
            role: role,
            content: content,
            timestamp: new Date().toISOString()
        });
        
        // حداکثر 100 پیام نگه‌داری می‌کنیم
        if (history.length > 100) {
            history = history.slice(-100);
        }
        
        localStorage.setItem(key, JSON.stringify(history));
    } catch (error) {
        console.error('خطا در ذخیره پیام:', error);
    }
}

/**
 * بارگذاری تاریخچه از LocalStorage
 */
function loadChatHistoryFromLocalStorage(phoneNumber) {
    try {
        const key = getChatHistoryKey(phoneNumber);
        const history = JSON.parse(localStorage.getItem(key) || '[]');
        return history;
    } catch (error) {
        console.error('خطا در بارگذاری تاریخچه:', error);
        return [];
    }
}

/**
 * پاک کردن تاریخچه از LocalStorage
 */
function clearChatHistoryFromLocalStorage(phoneNumber) {
    try {
        const key = getChatHistoryKey(phoneNumber);
        localStorage.removeItem(key);
    } catch (error) {
        console.error('خطا در پاک کردن تاریخچه:', error);
    }
}

// ========================================
// توابع کمکی
// ========================================

function validatePhoneNumber(phone) {
    const pattern = /^09\d{9}$/;
    return pattern.test(phone);
}

function showPhoneError(message) {
    elements.phoneError.textContent = message;
    elements.phoneInput.classList.add('error');
}

function clearPhoneError() {
    elements.phoneError.textContent = '';
    elements.phoneInput.classList.remove('error');
}

function showNotification(message, type = 'info') {
    elements.notification.textContent = message;
    elements.notification.className = `notification ${type}`;
    elements.notification.classList.add('show');
    
    setTimeout(() => {
        elements.notification.classList.remove('show');
    }, 4000);
}

function setLoading(button, isLoading) {
    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

function formatTime(date) {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleTimeString('fa-IR', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function scrollToBottom(smooth = true) {
    setTimeout(() => {
        elements.chatMessages.scrollTo({
            top: elements.chatMessages.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    }, 100);
}

function saveConversationId(id) {
    localStorage.setItem('conversationId', id);
    conversationId = id;
}

function loadConversationId() {
    return localStorage.getItem('conversationId');
}

function clearConversationId() {
    localStorage.removeItem('conversationId');
    conversationId = null;
}

// ========================================
// مدیریت پیام‌ها
// ========================================

function createMessageElement(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = isUser 
        ? '<svg viewBox="0 0 24 24" fill="none"><path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 11C14.2091 11 16 9.20914 16 7C16 4.79086 14.2091 3 12 3C9.79086 3 8 4.79086 8 7C8 9.20914 9.79086 11 12 11Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none"><path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="currentColor" stroke-width="2"/><path d="M9 22V12H15V22" stroke="currentColor" stroke-width="2"/></svg>';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // اگر Marked.js موجود است، از آن استفاده کن
    if (typeof marked !== 'undefined' && !isUser) {
        contentDiv.innerHTML = marked.parse(content);
    } else {
        contentDiv.textContent = content;
    }
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    timeSpan.textContent = formatTime(new Date());
    contentDiv.appendChild(timeSpan);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    return messageDiv;
}

function addMessage(content, isUser = false) {
    if (!content.trim()) return;
    
    const messageElement = createMessageElement(content, isUser);
    elements.chatMessages.appendChild(messageElement);
    scrollToBottom();
}

/**
 * افزودن پیام خالی برای ربات (برای شروع streaming)
 */
function addEmptyBotMessage() {
    const messageElement = createMessageElement('', false);
    elements.chatMessages.appendChild(messageElement);
    scrollToBottom();
    return messageElement;
}

/**
 * به‌روزرسانی پیام ربات (برای streaming)
 */
function updateBotMessage(content, messageElement = null) {
    // اگر المان پیام داده نشده، آخرین پیام ربات را پیدا کن
    if (!messageElement) {
        const messages = elements.chatMessages.querySelectorAll('.message.bot');
        messageElement = messages[messages.length - 1];
        
        // اگر پیام ربات وجود ندارد، خطا
        if (!messageElement) {
            console.error('No bot message to update');
            return;
        }
    }
    
    const contentDiv = messageElement.querySelector('.message-content');
    const timeSpan = contentDiv.querySelector('.message-time');
    const currentTime = timeSpan ? timeSpan.textContent : formatTime(new Date());
    
    // تبدیل Markdown به HTML
    if (typeof marked !== 'undefined') {
        try {
            contentDiv.innerHTML = marked.parse(content);
        } catch (e) {
            contentDiv.textContent = content;
        }
    } else {
        contentDiv.textContent = content;
    }
    
    const newTimeSpan = document.createElement('span');
    newTimeSpan.className = 'message-time';
    newTimeSpan.textContent = currentTime;
    contentDiv.appendChild(newTimeSpan);
    
    scrollToBottom();
}

function showTypingIndicator(show = true) {
    if (show) {
        elements.typingIndicator.classList.add('active');
    } else {
        elements.typingIndicator.classList.remove('active');
    }
    scrollToBottom();
}

function clearMessages() {
    elements.chatMessages.innerHTML = '';
}

/**
 * بارگذاری تاریخچه و نمایش در چت
 */
function loadAndDisplayChatHistory(phoneNumber) {
    const history = loadChatHistoryFromLocalStorage(phoneNumber);
    
    clearMessages();
    
    if (history.length > 0) {
        history.forEach(msg => {
            addMessage(msg.content, msg.role, false, msg.timestamp);
        });
        console.log(`✅ ${history.length} پیام از تاریخچه بارگذاری شد`);
    } else {
        console.log('ℹ️ تاریخچه‌ای برای نمایش وجود ندارد');
    }
}

// ========================================
// ارتباط با API
// ========================================

/**
 * شروع گفتگو با POST و دریافت Stream
 */
async function startChatWithStream(phoneNumber) {
    try {
        showTypingIndicator(true);
        
        // ایجاد پیام خالی برای ربات در ابتدا
        const botMessageElement = addEmptyBotMessage();
        showTypingIndicator(false); // مخفی کردن typing بعد از ایجاد پیام
        
        const response = await fetch(`${API_BASE_URL}/start_chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: phoneNumber
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullResponse = '';

        while (true) {
            const { value, done } = await reader.read();
            
            if (done) {
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    
                    if (data === '[DONE]') {
                        return;
                    }

                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.message) {
                            fullResponse = parsed.message;
                            // به‌روزرسانی پیام با ارسال المان مشخص
                            updateBotMessage(fullResponse, botMessageElement);
                        }
                    } catch (e) {
                        console.error('خطا در پردازش JSON:', e);
                    }
                }
            }
        }
    } catch (error) {
        // در صورت خطا، پیام خالی را حذف کنیم
        const messages = elements.chatMessages.querySelectorAll('.message.bot');
        const lastBotMessage = messages[messages.length - 1];
        if (lastBotMessage && !lastBotMessage.querySelector('.message-content').textContent.trim()) {
            lastBotMessage.remove();
        }
        throw error;
    }
}

/**
 * ارسال پیام با POST و دریافت Stream
 */
async function sendMessageWithStream(message) {
    try {
        showTypingIndicator(true);
        
        // تأخیر کوچک برای اطمینان از رندر شدن پیام کاربر
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // ایجاد پیام خالی برای ربات بلافاصله بعد از پیام کاربر
        const botMessageElement = addEmptyBotMessage();
        showTypingIndicator(false);
        
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                message: message
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullResponse = '';

        while (true) {
            const { value, done } = await reader.read();
            
            if (done) {
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    
                    if (data === '[DONE]') {
                        return;
                    }

                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.message) {
                            fullResponse = parsed.message;
                            // به‌روزرسانی پیام با ارسال المان مشخص
                            updateBotMessage(fullResponse, botMessageElement);
                        }
                    } catch (e) {
                        console.error('خطا در پردازش JSON:', e);
                    }
                }
            }
        }
    } catch (error) {
        // در صورت خطا، پیام خالی را حذف کنیم
        const messages = elements.chatMessages.querySelectorAll('.message.bot');
        const lastBotMessage = messages[messages.length - 1];
        if (lastBotMessage && !lastBotMessage.querySelector('.message-content').textContent.trim()) {
            lastBotMessage.remove();
        }
        showTypingIndicator(false);
        throw error;
    }
}

// ========================================
// هندلرهای رویداد
// ========================================

/**
 * شروع چت
 */
async function handleStartChat() {
    const phoneNumber = elements.phoneInput.value.trim();
    
    if (!phoneNumber) {
        showPhoneError('لطفاً شماره موبایل خود را وارد کنید');
        return;
    }
    
    if (!validatePhoneNumber(phoneNumber)) {
        showPhoneError('شماره موبایل نامعتبر است (مثال: 09123456789)');
        return;
    }
    
    clearPhoneError();
    setLoading(elements.startChatBtn, true);
    
    try {
        saveConversationId(phoneNumber);
        
        // نمایش صفحه چت
        elements.loginPage.classList.remove('active');
        elements.chatPage.classList.add('active');
        
        // بارگذاری تاریخچه قبلی
        loadAndDisplayChatHistory(phoneNumber);
        
        // شروع گفتگوی جدید
        await startChatWithStream(phoneNumber);
        
    } catch (error) {
        console.error('خطا در شروع چت:', error);
        showNotification('خطا در برقراری ارتباط. لطفاً دوباره تلاش کنید.', 'error');
        
        elements.chatPage.classList.remove('active');
        elements.loginPage.classList.add('active');
        clearConversationId();
    } finally {
        setLoading(elements.startChatBtn, false);
    }
}

/**
 * ارسال پیام
 */
async function handleSendMessage(event) {
    event.preventDefault();
    
    const message = elements.messageInput.value.trim();
    
    if (!message) return;
    
    // افزودن پیام کاربر
    addMessage(message, 'user', true);
    
    // پاک کردن فیلد ورودی
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';
    
    elements.sendBtn.disabled = true;
    
    try {
        await sendMessageWithStream(message);
    } catch (error) {
        console.error('خطا در ارسال پیام:', error);
        showNotification('خطا در ارسال پیام. لطفاً دوباره تلاش کنید.', 'error');
    } finally {
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

/**
 * بازگشت به صفحه ورود
 */
function handleBackToLogin() {
    if (confirm('آیا می‌خواهید از چت خارج شوید؟')) {
        clearMessages();
        
        elements.chatPage.classList.remove('active');
        elements.loginPage.classList.add('active');
        
        elements.phoneInput.value = '';
        elements.messageInput.value = '';
        clearPhoneError();
    }
}

/**
 * پاک کردن چت
 */
function handleClearChat() {
    if (confirm('آیا می‌خواهید تمام پیام‌ها را پاک کنید؟\n\n⚠️ این عملیت تاریخچه را از مرورگر شما حذف می‌کند.')) {
        clearMessages();
        
        if (conversationId) {
            clearChatHistoryFromLocalStorage(conversationId);
        }
        
        showNotification('تاریخچه چت پاک شد', 'success');
    }
}

/**
 * تنظیم ارتفاع خودکار textarea
 */
function handleTextareaResize() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = elements.messageInput.scrollHeight + 'px';
}

/**
 * ارسال با کلید Enter
 */
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleSendMessage(event);
    }
}

// ========================================
// ثبت رویدادها
// ========================================
function initializeEventListeners() {
    elements.startChatBtn.addEventListener('click', handleStartChat);
    elements.phoneInput.addEventListener('input', clearPhoneError);
    elements.phoneInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleStartChat();
        }
    });
    
    elements.messageForm.addEventListener('submit', handleSendMessage);
    elements.messageInput.addEventListener('input', handleTextareaResize);
    elements.messageInput.addEventListener('keypress', handleKeyPress);
    elements.backBtn.addEventListener('click', handleBackToLogin);
    elements.clearChatBtn.addEventListener('click', handleClearChat);
}

// ========================================
// راه‌اندازی اولیه
// ========================================
function initialize() {
    const savedId = loadConversationId();
    if (savedId) {
        elements.phoneInput.value = savedId;
    }
    
    initializeEventListeners();
    
    elements.phoneInput.focus();
    
    console.log('✅ چت‌بات آماده است');
    console.log('📱 شماره ذخیره‌شده:', savedId || 'ندارد');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}