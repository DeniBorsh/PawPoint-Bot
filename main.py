import telebot
from telebot import types
import sqlite3

TOKEN = ""
MODERS_LIST = [0, # Contaro
               0, # Тамерлан
               0, # Асхаб
               0, # Седа
               0] # wirotenshi
CONTARO = 0
CHANNEL_ID = '@pawpoint'
moderation_queue = []
photo_file_ids = {}

bot = telebot.TeleBot(TOKEN)
conn = sqlite3.connect('./data/database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS photos
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_id TEXT,
                description TEXT, lat REAL, lng REAL, status TEXT, username TEXT)''')
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

@bot.message_handler(commands=['reqmoder'])
def request_moderation(message):
    bot.send_message(CONTARO, f"Username: @{message.from_user.username}\nName: {message.from_user.first_name}\nID: {message.from_user.id}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not (message.from_user.id in photo_file_ids):
        try:
            file_id = message.photo[-1].file_id

            cursor.execute("INSERT INTO photos (user_id, file_id, status, username, description) VALUES (?, ?, ?, ?, ?)",
                        (message.from_user.id, file_id, "edit", "", ""))
            conn.commit()

            photo_file_ids[message.from_user.id] = file_id

            bot.send_message(message.chat.id, "Теперь отправьте местоположение уличного животного, а после, по желанию, описание")
        except Exception as e:
            bot.reply_to(message, "Произошла ошибка!")
    else:
        markup = types.InlineKeyboardMarkup(row_width=2)
        cancell_button = types.InlineKeyboardButton("Отменить", callback_data="cancell")
        finish_button = types.InlineKeyboardButton("Дополнить", callback_data="finish")
        markup.add(cancell_button, finish_button)

        bot.send_message(message.chat.id, "У вас имеется незавершенная публикация. Желаете ее дополнить или отменить?", reply_markup=markup)

@bot.message_handler(content_types=['location'])
def add_location(message):
    if message.from_user.id in photo_file_ids:
        file_id = photo_file_ids[message.from_user.id]
        lat = message.location.latitude
        lng = message.location.longitude

        cursor.execute("UPDATE photos SET lat = ?, lng = ? WHERE file_id = ?",
                       (lat, lng, file_id))
        conn.commit()

        location_description(message.chat.id)
    else:
        bot.reply_to(message, "Пожалуйста, сначала отправьте фотографию.")

def location_description(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    no_button = types.InlineKeyboardButton("Нет", callback_data="username")
    description_button = types.InlineKeyboardButton("Добавить описание", callback_data="add_description")
    markup.add(no_button, description_button)

    bot.send_message(chat_id, "Местоположение добавлено! Чтобы поменять местоположение, просто пришлите новое местоположение. Желаете добавить описание к фотографии?", reply_markup=markup)

def handle_done(user_id):
    file_id = photo_file_ids.get(user_id)

    cursor.execute('UPDATE photos SET status = ? WHERE file_id = ?', ("new", file_id))
    conn.commit()
    bot.send_message(user_id, 'Информация успешно отправлена на модерацию и скоро появится на канале. Спасибо за помощь уличным животным!')
    if photo_file_ids.get(user_id):
        del photo_file_ids[user_id]

def handle_username(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    no_button = types.InlineKeyboardButton("Нет", callback_data="add_nothing")
    link_button = types.InlineKeyboardButton("Ссылка", callback_data="add_link")
    first_name_button = types.InlineKeyboardButton("Имя", callback_data="add_first_name")
    markup.add(no_button, link_button, first_name_button)

    bot.send_message(chat_id, "Хотите ли вы, чтобы в посте отображалось ваше имя либо ссылка на ваш профиль?", reply_markup=markup)

def handle_urgency(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    done_button = types.InlineKeyboardButton("Завершить", callback_data="done")
    urgently_button = types.InlineKeyboardButton("❗️ Срочно", callback_data="urgency")
    markup.add(done_button, urgently_button)

    bot.send_message(chat_id, "Если животное требует срочного внимание, нажмите на соответствующую кнопку. И, пожалуйста, не делайте этого, если срочного внимания не требуется", reply_markup=markup)

def cancell_post(user_id):

    file_id = photo_file_ids.get(user_id)
    cursor.execute('DELETE FROM photos WHERE file_id = ?', (file_id,))
    conn.commit()

    if photo_file_ids.get(user_id):
        del photo_file_ids[user_id]
    bot.send_message(user_id, 'Публикация успешно отозвана. Для совершения новой публикации просто поделитель фотографией!')

def finish_post(chat_id):

    file_id = photo_file_ids.get(chat_id)

    cursor.execute("SELECT description, lat, username FROM photos WHERE file_id = ?", (file_id,))
    requests = cursor.fetchone()
    if requests:
        description, lat, username = requests
        if not lat:
            bot.send_message(chat_id, "Теперь отправьте местоположение уличного животного, а после, по желанию, описание")
        elif description == "":
            location_description(chat_id)
        elif username == "":
            handle_username(chat_id)
        else:
            handle_urgency(chat_id)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "done":
        handle_done(call.from_user.id)
    elif call.data == "add_description":
        bot.send_message(call.message.chat.id, 'Напишите описание для фотографии. Если вы передумали, пришлите точку')
        bot.register_next_step_handler(call.message, add_description, photo_file_ids.get(call.from_user.id))
    elif call.data == "urgency":
        file_id = photo_file_ids[call.from_user.id]
        handle_done(call.from_user.id)

        cursor.execute("SELECT id, description, lat, lng FROM photos WHERE status = 'new' OR status = 'delayed' AND file_id = ?", (file_id,))
        requests = cursor.fetchall()

        request_id, description, lat, lng = requests[0]
        markup = types.InlineKeyboardMarkup(row_width=3)
        accept_button = types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_{request_id}")
        reject_button = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
        delay_button = types.InlineKeyboardButton("⏰ Отложить", callback_data=f"delay_{request_id}")
        markup.add(accept_button, reject_button, delay_button)
        if call.from_user.username:
            username = f"@{call.from_user.username}"
        else:
            username = call.from_user.first_name
        for id in MODERS_LIST:
            google_maps_url = f"https://www.google.com/maps/place/{lat},{lng}"
            bot.send_photo(chat_id=id, photo=file_id, caption=f"Автор: {username}\nОписание: {description}\n[Местоположение]({google_maps_url})", reply_markup=markup, parse_mode='Markdown')
    elif call.data == "add_link":
        file_id = photo_file_ids[call.from_user.id]
        cursor.execute('UPDATE photos SET username = ? WHERE file_id = ?', (f"@{call.from_user.username}", file_id))
        conn.commit()
        handle_urgency(call.from_user.id)
    elif call.data == "add_first_name":
        file_id = photo_file_ids[call.from_user.id]
        cursor.execute('UPDATE photos SET username = ? WHERE file_id = ?', (f"{call.from_user.first_name}", file_id))
        conn.commit()
        handle_urgency(call.from_user.id)
    elif call.data == "add_nothing":
        handle_urgency(call.from_user.id)
    elif call.data == "username":
        handle_username(call.from_user.id)
    elif call.data == "cancell":
        cancell_post(call.from_user.id)
    elif call.data == "finish":
        finish_post(call.from_user.id)
    else:
        action, request_id = call.data.split('_')
        cursor.execute("SELECT status FROM photos WHERE id = ?", (request_id,))
        result = cursor.fetchone()
        if result and result[0] in ['new', 'delayed']:
            if action == 'accept':
                cursor.execute("UPDATE photos SET status = 'accepted' WHERE id = ?", (request_id,))
                conn.commit()

                cursor.execute("SELECT file_id, description, lat, lng, username FROM photos WHERE id = ?", (request_id,))
                photo_info = cursor.fetchone()

                if photo_info:
                    file_id, description, lat, lng, username = photo_info
                    if len(description) > 0:
                        description = f"Комментарий автора: {description}\n"

                    if len(username) > 0:
                        username = f"Автор: {username}\n"

                    google_maps_url = f"https://www.google.com/maps/place/{lat},{lng}"
                    message_text = f"{username}{description}[Местоположение]({google_maps_url})"

                    bot.send_photo(CHANNEL_ID, file_id, caption=message_text, parse_mode='Markdown')

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
    bot.delete_message(call.message.chat.id, call.message.message_id)


def add_description(message, file_id):
    if message.content_type == 'text':
        if (message.text == "."):
            handle_username(message.chat.id)
        cursor.execute('UPDATE photos SET description = ? WHERE file_id = ?', (message.text, file_id))
        conn.commit()

        bot.reply_to(message, "Описание добавлено")
        handle_username(message.chat.id)
    else:
        bot.reply_to(message, "Пожалуйста, отправьте текстовое описание. Если вы передумали, пришлите точку")
        bot.register_next_step_handler(message, add_description, file_id)

@bot.message_handler(commands=['moderate'])
def moderate_command(message):
    moderate(message.from_user.id)

def moderate(user_id):
    global moderation_queue
    if user_id in MODERS_LIST:
        if not moderation_queue:
            cursor.execute("SELECT id, user_id, file_id, description, lat, lng FROM photos WHERE status = 'new' OR status = 'delayed'")
            moderation_queue = cursor.fetchall()

        if moderation_queue:
            request = moderation_queue.pop(0)
            request_id, uid, file_id, description, lat, lng = request
            markup = types.InlineKeyboardMarkup(row_width=3)
            accept_button = types.InlineKeyboardButton("✅ Принять", callback_data=f"accept_{request_id}")
            reject_button = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
            delay_button = types.InlineKeyboardButton("⏰ Отложить", callback_data=f"delay_{request_id}")
            markup.add(accept_button, reject_button, delay_button)

            google_maps_url = f"https://www.google.com/maps/place/{lat},{lng}"
            bot.send_photo(chat_id=user_id, photo=file_id, caption=f"Автор: {get_username(uid)}\nОписание: {description}\n[Местоположение]({google_maps_url})", reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(user_id, "Нет постов, ожидающих модерации.")
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
        cursor.execute("SELECT id FROM photos WHERE status = 'rejected'")
        rejected_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status = 'delayed'")
        delayed_posts = cursor.fetchall()
        cursor.execute("SELECT id FROM photos WHERE status = 'edit'")
        editing_posts = cursor.fetchall()

        bot.send_message(user_id, f"Новые публикации: {len(new_posts)}\nПринятые: {len(accepted_posts)}\nОтклоненные: {len(rejected_posts)}\nОтложенные: {len(delayed_posts)}\nЕще не готовые: {len(editing_posts)}\n")
    else:
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")

@bot.message_handler(commands=['forcontaroonly'])
def for_contaro_only(message):
    pass

@bot.message_handler(commands=['cleanup'])
def cleanup(message):
    user_id = message.from_user.id
    if user_id in MODERS_LIST:
        cursor.execute("UPDATE photos SET status = 'deleted' WHERE status = 'edit'")
        conn.commit()
        bot.send_message(user_id, "Очистка успешно завершена")
    else:
        bot.send_message(user_id, "У вас нет прав для выполнения этой команды.")

def get_username(user_id):
    try:
        chat_info = bot.get_chat(user_id)
        if chat_info.username:
            return f"@{chat_info.username}"
        else:
            return chat_info.first_name
        # Возвращаем username пользователя
    except Exception as e:
        return ""

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    if message.text == "🛡️ Модерация":
        moderate_command(message)
    elif message.text == "🗑️ Очистить фотографии":
        cleanup(message)
    elif message.text == "📝 Информация о БД":
        get_info(message)
    else:
        if photo_file_ids.get(message.from_user.id):
            bot.send_message(message.chat.id, "Пришлите местоположение в виде геоданных. Если уже присылали - то продолжите навигацию по кнопкам, пожалуйста)")
        else:
            bot.send_message(message.chat.id, "Сначала пришлите фотографию")

bot.polling(none_stop=True)