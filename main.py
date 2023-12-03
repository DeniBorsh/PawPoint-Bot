import telebot
from telebot import types
import sqlite3
import os

TOKEN = ""
MODERS_LIST = [0, # Contaro
               0, # Тамерлан
               0, # Асхаб
               0] # Седа
CONTARO = 0
CHANNEL_ID = '@pawpoint'
moderation_queue = []
photo_file_ids = {}

bot = telebot.TeleBot(TOKEN)
conn = sqlite3.connect('./data/database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS photos
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_id TEXT,
                file_path TEXT, description TEXT, lat REAL, lng REAL, status TEXT, username TEXT)''')
conn.commit()


@bot.message_handler(commands=['start'])
def onstart(message):
    user_id = message.from_user.id
    if user_id in MODERS_LIST:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        moderate_button = types.KeyboardButton("🛡️ Модерация")
        cleanup_button = types.KeyboardButton("🗑️ Очистить фотографии")
        info_button = types.KeyboardButton("📝 Информация о БД")
        markup.row(moderate_button, cleanup_button)
        markup.row(info_button)
        greeting = f"Привет, администратор {message.from_user.first_name}!"
        bot.send_message(message.chat.id, greeting, reply_markup=markup)
    else:
        greeting = f"Привет, {message.from_user.first_name}! Если вы хотите поделиться фотографией уличного животного, то я жду!"
        bot.send_message(message.chat.id, greeting)

@bot.message_handler(func=lambda message: message.text in ["🛡️ Модерация", "🗑️ Очистить фотографии", "📝 Информация о БД"])
def text_handler(message):
    if message.text == "🛡️ Модерация":
        moderate_command(message)
    elif message.text == "🗑️ Очистить фотографии":
        cleanup(message)
    elif message.text == "📝 Информация о БД":
        get_info(message)

@bot.message_handler(commands=['reqmoder'])
def request_moderation(message):
    bot.send_message(CONTARO, f"Username: @{message.from_user.username}\nName: {message.from_user.first_name}\nID: {message.from_user.id}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:

        file_info = bot.get_file(message.photo[-1].file_id)

        downloaded_file = bot.download_file(file_info.file_path)

        file_local_path = os.path.join("./data/photo", file_info.file_id + ".jpg")
        with open(file_local_path, "wb") as new_file:
            new_file.write(downloaded_file)

        cursor.execute("INSERT INTO photos (user_id, file_id, file_path, status, username, description) VALUES (?, ?, ?, ?, ?, ?)",
                       (message.from_user.id, file_info.file_id, file_local_path, "edit", "", ""))
        conn.commit()

        photo_file_ids[message.from_user.id] = file_info.file_id

        bot.send_message(message.chat.id, "Теперь отправьте местоположение уличного животного, а после, по желанию, описание")
    except Exception as e:
        bot.reply_to(message, "Произошла ошибка!")

@bot.message_handler(content_types=['location'])
def add_location(message):
    if message.from_user.id in photo_file_ids:
        file_id = photo_file_ids[message.from_user.id]
        lat = message.location.latitude
        lng = message.location.longitude

        cursor.execute("UPDATE photos SET lat = ?, lng = ? WHERE file_id = ?",
                       (lat, lng, file_id))
        conn.commit()

        markup = types.InlineKeyboardMarkup(row_width=2)
        no_button = types.InlineKeyboardButton("Нет", callback_data="username")
        description_button = types.InlineKeyboardButton("Добавить описание", callback_data="add_description")
        markup.add(no_button, description_button)

        bot.reply_to(message, "Местоположение добавлено! Чтобы поменять местоположение, просто пришлите новое местоположение. Желаете добавить описание к фотографии?", reply_markup=markup)
    else:
        bot.reply_to(message, "Пожалуйста, сначала отправьте фотографию.")

def handle_done(user_id):
    if photo_file_ids.get(user_id):
        file_id = photo_file_ids[user_id]
    cursor.execute('UPDATE photos SET status = ? WHERE file_id = ?', ("new", file_id))
    conn.commit()
    bot.send_message(user_id, 'Информация успешно отправлена на модерацию и скоро появится на канале. Спасибо за помощь уличным животным!')
    del photo_file_ids[user_id]

def handle_username(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    no_button = types.InlineKeyboardButton("Нет", callback_data="add_nothing")
    link_button = types.InlineKeyboardButton("Ссылка", callback_data="add_link")
    first_name_button = types.InlineKeyboardButton("Имя", callback_data="add_first_name")
    markup.add(no_button, link_button, first_name_button)

    bot.send_message(message.chat.id, "Хотите ли вы, чтобы в посте отображалось ваше имя либо ссылка на ваш профиль?", reply_markup=markup)

def handle_urgency(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    done_button = types.InlineKeyboardButton("Завершить", callback_data="done")
    urgently_button = types.InlineKeyboardButton("❗️ Срочно", callback_data="urgency")
    markup.add(done_button, urgently_button)

    bot.reply_to(message, "Если животное требует срочного внимание, нажмите на соответствующую кнопку. И, пожалуйста, не делайте этого, если срочного внимания не требуется", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "done":
        handle_done(call.from_user.id)
    elif call.data == "add_description":
        bot.send_message(call.message.chat.id, 'Напишите описание для фотографии')
        bot.register_next_step_handler(call.message, add_description, photo_file_ids.get(call.from_user.id))
    elif call.data == "urgency":
        file_id = photo_file_ids[call.from_user.id]
        handle_done(call.from_user.id)

        cursor.execute("SELECT id, file_path, description, lat, lng FROM photos WHERE status = 'new' OR status = 'delayed' AND file_id = ?", (file_id,))
        requests = cursor.fetchall()

        request_id, file_path, description, lat, lng = requests[0]
        markup = types.InlineKeyboardMarkup(row_width=3)
        accept_button = types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_{request_id}")
        reject_button = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
        delay_button = types.InlineKeyboardButton("⏰ Отложить", callback_data=f"delay_{request_id}")
        markup.add(accept_button, reject_button, delay_button)
        for id in MODERS_LIST:
            bot.send_photo(chat_id=id, photo=open(file_path, 'rb'), caption=f"Описание: {description}\nМестоположение: {lat}, {lng}", reply_markup=markup)
    elif call.data == "add_link":
        file_id = photo_file_ids[call.from_user.id]
        cursor.execute('UPDATE photos SET username = ? WHERE file_id = ?', (f"@{call.from_user.username}", file_id))
        conn.commit()
        handle_urgency(call.message)
    elif call.data == "add_first_name":
        file_id = photo_file_ids[call.from_user.id]
        cursor.execute('UPDATE photos SET username = ? WHERE file_id = ?', (f"{call.from_user.first_name}", file_id))
        conn.commit()
        handle_urgency(call.message)
    elif call.data == "add_nothing":
        handle_urgency(call.message)
    elif call.data == "username":
        handle_username(call.message)
    else:
        action, request_id = call.data.split('_')
        cursor.execute("SELECT status FROM photos WHERE id = ?", (request_id,))
        result = cursor.fetchone()
        if result and result[0] in ['new', 'delayed']:
            if action == 'accept':
                cursor.execute("UPDATE photos SET status = 'accepted' WHERE id = ?", (request_id,))
                conn.commit()

                cursor.execute("SELECT file_path, description, lat, lng, username FROM photos WHERE id = ?", (request_id,))
                photo_info = cursor.fetchone()

                if photo_info:
                    file_path, description, lat, lng, username = photo_info
                    if len(description) > 0:
                        description = f"Комментарий автора: {description}\n"

                    if len(username) > 0:
                        username = f"Автор: {username}\n"

                    google_maps_url = f"https://www.google.com/maps/place/{lat},{lng}"
                    message_text = f"{username}{description}[Местоположение]({google_maps_url})"

                    with open(file_path, 'rb') as photo:
                        bot.send_photo(CHANNEL_ID, photo, caption=message_text, parse_mode='Markdown')

            elif action == 'reject':
                cursor.execute("UPDATE photos SET status = 'rejected' WHERE id = ?", (request_id,))
            elif action == 'delay':
                cursor.execute("UPDATE photos SET status = 'delayed' WHERE id = ?", (request_id,))
            conn.commit()
            bot.answer_callback_query(call.id, f"Заявка {action} для файла {request_id}")
        else:
            bot.answer_callback_query(call.id, "Этот пост уже обработан другим модератором.")
            bot.send_message(call.message.chat.id, "Этот пост уже обработан другим модератором")

        moderate(call.from_user.id)
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)


def add_description(message, file_id):
    cursor.execute('UPDATE photos SET description = ? WHERE file_id = ?', (message.text, file_id))
    conn.commit()        
    bot.reply_to(message, "Описание добавлено")
    handle_username(message)

@bot.message_handler(commands=['moderate'])
def moderate_command(message):
    moderate(message.from_user.id)

def moderate(user_id):
    global moderation_queue
    if user_id in MODERS_LIST:
        if not moderation_queue:
            cursor.execute("SELECT id, file_path, description, lat, lng FROM photos WHERE status = 'new' OR status = 'delayed'")
            moderation_queue = cursor.fetchall()

        if moderation_queue:
            request = moderation_queue.pop(0)
            request_id, file_path, description, lat, lng = request
            markup = types.InlineKeyboardMarkup(row_width=3)
            accept_button = types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_{request_id}")
            reject_button = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
            delay_button = types.InlineKeyboardButton("⏰ Отложить", callback_data=f"delay_{request_id}")
            markup.add(accept_button, reject_button, delay_button)
            bot.send_photo(chat_id=user_id, photo=open(file_path, 'rb'), caption=f"Описание: {description}\nМестоположение: {lat}, {lng}", reply_markup=markup)
        else:
            bot.send_message(user_id, "Нет постов, ожидающих модерации.")
    else:
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")

@bot.message_handler(commands=['cleanup'])
def cleanup(message):
    user_id = message.from_user.id
    if user_id in MODERS_LIST:
        cursor.execute("SELECT id, file_path FROM photos WHERE status in ('rejected', 'edit')")
        entries_to_delete = cursor.fetchall()

        for entry in entries_to_delete:
            photo_id, file_path = entry

            if os.path.exists(file_path):
                os.remove(file_path)

            cursor.execute("UPDATE photos SET status = ? WHERE id = ?", ("deleted", photo_id))
        conn.commit()
        bot.send_message(user_id, "Очистка успешно завершена")
    else:
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")

@bot.message_handler(commands=['info'])
def get_info(message):
    user_id = message.from_user.id
    if user_id in MODERS_LIST:
        cursor.execute("SELECT id FROM photos WHERE status = 'new'")
        new_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status = 'accepted'")
        accepted_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status IN ('rejected', 'deleted')")
        rejected_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status = 'delayed'")
        delayed_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status = 'edit'")
        editing_posts = cursor.fetchall()

        bot.send_message(user_id, f"Новые публикации: {len(new_posts)}\nПринятые: {len(accepted_posts)}\nОтклоненные: {len(rejected_posts)}\nОтложенные: {len(delayed_posts)}\nЕще не готовые: {len(editing_posts)}\n")
    else:
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")

bot.polling(none_stop=True)