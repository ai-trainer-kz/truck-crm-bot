import os
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import Command

import psycopg2

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_ID = 8398266271 

# ================= BOT =================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= DATABASE =================

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True

cursor = conn.cursor()

# ================= TABLES =================

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,
    name TEXT,
    phone TEXT,
    visits INTEGER DEFAULT 0,
    total_paid INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    title TEXT,
    price INTEGER,
    quantity INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS masters (
    id SERIAL PRIMARY KEY,
    name TEXT,
    specialty TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER,
    product TEXT,
    truck TEXT,
    vin TEXT,
    phone TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
)
""")

# ================= KEYBOARDS =================

client_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚚 Каталог")
        ],
        [
            KeyboardButton(text="🛢 Масла"),
            KeyboardButton(text="🔧 Фильтры")
        ],
        [
            KeyboardButton(text="⚙️ Запчасти"),
            KeyboardButton(text="🔥 Акции")
        ],
        [
            KeyboardButton(text="📦 Оставить заявку")
        ],
        [
            KeyboardButton(text="📍 Адрес"),
            KeyboardButton(text="📞 Контакты")
        ]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📦 Заявки"),
            KeyboardButton(text="🏬 Остатки")
        ],
        [
            KeyboardButton(text="👥 Клиенты"),
            KeyboardButton(text="📊 Статистика")
        ],
        [
            KeyboardButton(text="➕ Добавить товар"),
            KeyboardButton(text="❌ Удалить товар")
        ],
        [
            KeyboardButton(text="📢 Рассылка")
        ]
    ],
    resize_keyboard=True
)

# ================= START =================

@dp.message(Command("start"))
async def start_cmd(message: Message):

    user_id = message.from_user.id
    full_name = message.from_user.full_name

    cursor.execute(
        "SELECT * FROM clients WHERE tg_id = %s",
        (user_id,)
    )

    client = cursor.fetchone()

    if not client:
        cursor.execute(
            """
            INSERT INTO clients (tg_id, name)
            VALUES (%s, %s)
            """,
            (user_id, full_name)
        )

    text = (
        "🚚 Добро пожаловать в MotorParts Group\n\n"
        "Запчасти для китайских грузовиков,\n"
        "масла, фильтры и расходники.\n\n"
        "Выберите раздел ниже 👇"
    )

    await message.answer(
        text,
        reply_markup=client_kb
    )

# ================= ADMIN =================

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM clients")
    users_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_count = cursor.fetchone()[0]

    text = (
        f"👨‍💼 Админ панель\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"📅 Записей: {appointments_count}"
    )

    await message.answer(
        text,
        reply_markup=admin_kb
    )

# ================= CLIENT MENU =================
@dp.message(F.text == "📦 Оставить заявку")
async def booking(message: Message):

    text = (
    "📦 Заявка на запчасти\n\n"
    "Отправьте сообщением:\n\n"
    "1. Что нужно\n"
    "2. Марку грузовика\n"
    "3. Фото или VIN (если есть)\n"
    "4. Ваш телефон\n\n"
    "Пример:\n\n"
    "Фильтр масляный\n"
    "Howo\n"
    "VIN: LGGR...\n"
    "+7 777 123 45 67"
)

    await message.answer(text)

@dp.message(F.text.regexp(r".+\n.+\n.+\n.+"))
async def save_booking(message: Message):

    try:

        text = message.text.strip()

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if len(lines) != 4:
            return

        product = lines[0]
        truck = lines[1]
        vin = lines[2]
        phone = lines[3]
        
        # Получаем клиента
        cursor.execute(
            """
            SELECT id, visits
            FROM clients
            WHERE tg_id = %s
            """,
            (message.from_user.id,)
        )

        client = cursor.fetchone()

        # Если клиента нет — создаем
        if not client:

            cursor.execute(
                """
                INSERT INTO clients (tg_id, name, visits)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    message.from_user.id,
                    message.from_user.full_name,
                    0
                )
            )

            client_id = cursor.fetchone()[0]
            current_visits = 0

        else:

            client_id = client[0]
            current_visits = client[1]

        # Сохраняем заявку
        cursor.execute(
            """
            INSERT INTO appointments
            (client_id, product, truck, vin, phone)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                client_id,
                product,
                truck,
                vin,
                phone
            )
        )

        # Обновляем визиты
        cursor.execute(
            """
            UPDATE clients
            SET visits = %s
            WHERE id = %s
            """,
            (
                current_visits + 1,
                client_id
            )
        )

        conn.commit()

        await message.answer(
            f"✅ Заявка отправлена!\n\n"
            f"📦 Товар: {product}"
        )

        # Уведомление админу
        await bot.send_message(
            ADMIN_ID,
            f"📥 Новая заявка!\n\n"
            f"👤 Клиент: {message.from_user.full_name}\n"
            f"📦 Товар: {product}"
        )

    except Exception as e:

        print("BOOKING ERROR:", e)

        await message.answer(
            f"❌ Ошибка записи:\n{e}"
        )
        
@dp.message(F.text == "💅 Услуги")
async def services(message: Message):

    cursor.execute("SELECT title, price FROM services")

    services_list = cursor.fetchall()

    if not services_list:
        await message.answer("Услуги пока не добавлены.")
        return

    text = "💅 Наши услуги:\n\n"

    for service in services_list:
        text += f"• {service[0]} — {service[1]}₸\n"

    await message.answer(text)

@dp.message(F.text == "👩‍🔬 Мастера")
async def masters(message: Message):

    cursor.execute("SELECT name, specialty FROM masters")

    masters_list = cursor.fetchall()

    if not masters_list:
        await message.answer("Мастера пока не добавлены.")
        return

    text = "👩‍🔬 Наши мастера:\n\n"

    for master in masters_list:
        text += f"• {master[0]} — {master[1]}\n"

    await message.answer(text)

@dp.message(F.text == "🕒 Мои записи")
async def my_appointments(message: Message):

    user_id = message.from_user.id

    cursor.execute(
        "SELECT id FROM clients WHERE tg_id = %s",
        (user_id,)
    )

    client = cursor.fetchone()

    if not client:
        await message.answer("Вы не зарегистрированы.")
        return

    client_id = client[0]

    cursor.execute(
        """
        SELECT product, truck, vin, phone
        FROM appointments
        WHERE client_id = %s
        ORDER BY id DESC
        """,
        (client_id,)
    )

    appointments = cursor.fetchall()

    if not appointments:
        await message.answer("У вас пока нет записей.")
        return

    text = "🕒 Ваши записи:\n\n"

    for item in appointments:

        product = item[0]
        truck = item[1]
        vin = item[2]
        phone = item[3]
    
        text += (
            f"📦 Товар: {product}\n"
            f"🚚 Грузовик: {truck}\n"
            f"🆔 VIN: {vin}\n"
            f"📞 Телефон: {phone}\n\n"
        )
    await message.answer(text)

@dp.message(F.text == "❌ Отменить запись")
async def cancel_booking(message: Message):

    try:

        user_id = message.from_user.id

        cursor.execute(
            """
            SELECT id, visits
            FROM clients
            WHERE tg_id = %s
            """,
            (user_id,)
        )

        client = cursor.fetchone()

        if not client:
            await message.answer("❌ У вас нет заявок.")
            return

        client_id = client[0]
        current_visits = client[1]

        cursor.execute(
            """
            SELECT id, product
            FROM appointments
            WHERE client_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (client_id,)
        )

        appointment = cursor.fetchone()

        if not appointment:
            await message.answer("❌ Заявок не найдено.")
            return

        appointment_id = appointment[0]
        product = appointment[1]

        cursor.execute(
            """
            DELETE FROM appointments
            WHERE id = %s
            """,
            (appointment_id,)
        )

        if current_visits > 0:

            cursor.execute(
                """
                UPDATE clients
                SET visits = %s
                WHERE id = %s
                """,
                (
                    current_visits - 1,
                    client_id
                )
            )

        conn.commit()

        await message.answer(
            f"✅ Заявка отменена.\n\n"
            f"📦 Товар: {product}"
        )

    except Exception as e:

        print("CANCEL ERROR:", e)

        await message.answer(
            f"❌ Ошибка:\n{e}"
        )
    except Exception as e:

        print("CANCEL ERROR:", e)

        await message.answer(
            f"❌ Ошибка:\n{e}"
        )
        
@dp.message(F.text == "💰 Прайс")
async def price(message: Message):

    cursor.execute("SELECT title, price FROM services")

    services_list = cursor.fetchall()

    if not services_list:
        await message.answer("Прайс пока пуст.")
        return

    text = "💰 Прайс:\n\n"

    for service in services_list:
        text += f"{service[0]} — {service[1]}₸\n"

    await message.answer(text)

@dp.message(F.text == "📍 Адрес")
async def address(message: Message):

    text = (
        "📍 Наш адрес:\n\n"
        "г. Алматы\n"
        "ул. Примерная 25"
    )

    await message.answer(text)

@dp.message(F.text == "📞 Контакты")
async def contacts(message: Message):

    text = (
        "📞 Контакты:\n\n"
        "+7 777 777 77 77\n"
        "@your_instagram"
    )

    await message.answer(text)

# ================= ADMIN FUNCTIONS =================
@dp.message(F.text == "📦 Все заявки")
async def all_appointments(message: Message):

    cursor.execute("""
        SELECT product, truck, vin, phone
        FROM appointments
        ORDER BY id DESC
    """)

    appointments = cursor.fetchall()

    if not appointments:
        await message.answer("Заявок пока нет.")
        return

    text = "📦 Все заявки:\n\n"

    for app in appointments:

        product = app[0]
        truck = app[1]
        vin = app[2]
        phone = app[3]

        text += (
            f"📦 Товар: {product}\n"
            f"🚚 Грузовик: {truck}\n"
            f"🆔 VIN: {vin}\n"
            f"📞 Телефон: {phone}\n\n"
        )

    await message.answer(text)
    
@dp.message(F.text == "👥 Клиенты")
async def clients_list(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
    SELECT name, visits, total_paid
    FROM clients
    WHERE name != 'AI Учитель Поддержка'
    ORDER BY id DESC
    """)

    clients = cursor.fetchall()

    if not clients:
        await message.answer("Клиентов пока нет.")
        return

    text = "👥 Клиенты:\n\n"

    for client in clients:
        text += (
            f"👤 {client[0]}\n"
            f"📅 Визитов: {client[1]}\n"
            f"💰 Потратил: {client[2]}₸\n\n"
        )

    await message.answer(text)

@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM clients")
    clients_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_count = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_paid),0) FROM clients")
    total_money = cursor.fetchone()[0]

    text = (
        "📊 Статистика\n\n"
        f"👥 Клиентов: {clients_count}\n"
        f"📅 📦 Заявки: {appointments_count}\n"
        f"💰 Общая выручка: {total_money}₸"
    )

    await message.answer(text)

@dp.message(F.text == "➕ Добавить услугу")
async def add_service(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    text = (
        "Чтобы добавить услугу,\n"
        "отправьте так:\n\n"
        "Название,Категория,Цена"
    )

    await message.answer(text)

@dp.message(F.text == "➕ Добавить мастера")
async def add_master(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    text = (
        "Чтобы добавить мастера,\n"
        "отправьте так:\n\n"
        "Алина,Маникюр"
    )

    await message.answer(text)

@dp.message(F.text == "📢 Рассылка")
async def mailing(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Отправьте текст для рассылки."
    )

# ================= AUTO ADD SERVICE =================

@dp.message(F.text.contains(","))
async def text_handler(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    text = message.text

    # Добавление услуги
    if "," in text:

        parts = text.split(",")

        # SERVICE
        if len(parts) == 3:

            title = parts[0]
            price = int(parts[1])
            quantity = int(parts[2])
        
            cursor.execute(
                """
                INSERT INTO products
                (title, price, quantity)
                VALUES (%s, %s, %s)
                """,
                (title, price, quantity)
            )
        
            await message.answer(
                "✅ Товар добавлен"
            )

        # MASTER
        elif len(parts) == 3:

            title = parts[0]
            price = int(parts[1])
            quantity = int(parts[2])
        
            cursor.execute(
                """
                INSERT INTO products (title, price, quantity)
                VALUES (%s, %s, %s)
                """,
                (title, price, quantity)
            )
        
            await message.answer("✅ Товар добавлен")

@dp.message(F.text == "🚚 Каталог")
async def catalog(message: Message):

    try:

        cursor.execute("""
            SELECT title, price, quantity
            FROM products
            WHERE quantity > 0
            ORDER BY id DESC
        """)

        products = cursor.fetchall()

        if not products:
            await message.answer("🚚 Каталог пуст.")
            return

        text = "🚚 Каталог:\n\n"

        for product in products:

            text += (
                f"📦 {product[0]}\n"
                f"💰 {product[1]}₸\n\n"
            )

        await message.answer(text)

    except Exception as e:

        print("CATALOG ERROR:", e)

        await message.answer(f"❌ Ошибка каталога:\n{e}")
    
@dp.message(F.text == "🛢 Масла")
async def oils(message: Message):
    await message.answer(
        "🛢 Масла в наличии:\n\n"
        "• Shell Rimula\n"
        "• Mobil Delvac\n"
        "• ZIC\n"
        "• Sinotruk\n\n"
        "Отправьте марку грузовика для подбора."
    )

@dp.message(F.text == "🔧 Фильтры")
async def filters(message: Message):
    await message.answer(
        "🔧 Фильтры:\n\n"
        "• Масляные\n"
        "• Воздушные\n"
        "• Топливные\n"
        "• Салонные\n\n"
        "Напишите модель грузовика."
    )


@dp.message(F.text == "⚙️ Запчасти")
async def parts(message: Message):
    await message.answer(
        "⚙️ Запчасти для китайских грузовиков:\n\n"
        "• HOWO\n"
        "• SHACMAN\n"
        "• FAW\n"
        "• FOTON\n\n"
        "Отправьте фото или VIN."
    )


@dp.message(F.text == "🔥 Акции")
async def sales(message: Message):
    await message.answer(
        "🔥 Акции недели:\n\n"
        "• Скидки на масла\n"
        "• Фильтры оптом\n"
        "• Бесплатный подбор запчастей"
    )

# ================= MAIN ================
async def main():

    print("CRM BOT STARTED")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
