import telebot
import os
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

#bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
bot = None
alert_manager_ref = None

def send_alert_with_button(img_path, caption, level):
    return
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("[Telegram Bot] Không thể gửi cảnh báo: Token hoặc Chat ID chưa được thiết lập.")
        return
        
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton(text="Xác nhận ✅", callback_data=f"ack_alert_{level}")
    markup.add(btn)
    
    try:
        with open(img_path, "rb") as photo:
            bot.send_photo(TELEGRAM_CHAT_ID, photo, caption=caption, reply_markup=markup)
    except Exception as e:
        print(f"[Telegram Bot] Lỗi khi gửi ảnh lên Telegram: {e}")

# @bot.callback_query_handler(func=lambda call: call.data.startswith('ack_alert_'))
# def ack_alert_callback(call):
#     global alert_manager_ref
    
#     try:
#         acked_level = int(call.data.split('_')[-1])
#         message_send_time = call.message.date  # Unix timestamp from Telegram
        
#         if alert_manager_ref is not None:
#             alert_manager_ref.user_feedback_received(acked_level, message_send_time)
            
#         # Sửa tin nhắn gốc để xóa nút bấm và thêm trạng thái xác nhận
#         new_caption = (call.message.caption or "") + "\n\n ĐÃ XÁC NHẬN 🟢 "
#         bot.edit_message_caption(caption=new_caption, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        
#         # Trả lời lại callback query để dừng hiệu ứng vòng chờ loading trên app
#         bot.answer_callback_query(call.id, "Đã xác nhận cảnh báo!")
#     except Exception as e:
#         print(f"[Telegram Bot] Lỗi khi xử lý callback từ Telegram: {e}")

def start_bot_thread(manager_instance):
    return
    global alert_manager_ref
    alert_manager_ref = manager_instance
    
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("[Telegram Bot] Token chưa cài đặt. Luồng chờ tin nhắn sẽ không được khởi động.")
        return
        
    polling_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    polling_thread.start()
    print("[Telegram Bot] Luồng kết nối trực tiếp BOT Telegram đã khởi động thành công.")
