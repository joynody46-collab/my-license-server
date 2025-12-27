import os
import datetime
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Получаем настройки
DATABASE_URL = os.environ.get("DATABASE_URL")
API_SECRET = os.environ.get("API_SECRET")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Создает таблицу, если её нет"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                hwid VARCHAR(255) PRIMARY KEY,
                expiry_date DATE NOT NULL
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("База данных проверена/создана.")
    except Exception as e:
        print(f"Ошибка БД: {e}")

# Инициализация при старте (если переменная задана)
if DATABASE_URL:
    init_db()

@app.route('/')
def home():
    return "License Server is Live!"

# === 1. ПРОВЕРКА ЛИЦЕНЗИИ ===
@app.route('/check', methods=['POST'])
def check():
    data = request.json or {}
    hwid = data.get('hwid')
    
    if not hwid:
        return jsonify({"status": "error", "message": "No HWID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT expiry_date FROM licenses WHERE hwid = %s", (hwid,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            expiry = result[0]
            if expiry >= datetime.date.today():
                return jsonify({"status": "active", "date": str(expiry)})
            else:
                return jsonify({"status": "expired", "date": str(expiry)})
        return jsonify({"status": "not_found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 2. ДОБАВЛЕНИЕ / ПРОДЛЕНИЕ / БАН ===
@app.route('/add', methods=['POST'])
def add_license():
    data = request.json or {}
    if data.get('secret') != API_SECRET:
        return jsonify({"error": "Forbidden"}), 403

    hwid = data.get('hwid')
    days = int(data.get('days', 30))
    mode = data.get('mode', 'set') # 'set' = установить, 'add' = продлить
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Получаем текущую дату окончания (если есть)
        cur.execute("SELECT expiry_date FROM licenses WHERE hwid = %s", (hwid,))
        row = cur.fetchone()
        
        today = datetime.date.today()
        current_expiry = row[0] if row else today

        # Логика расчета
        if mode == 'add':
            # Если продлеваем: берем максимум от (сегодня или дата_окончания) + дни
            start_date = max(current_expiry, today)
            new_date = start_date + datetime.timedelta(days=days)
        else:
            # Если 'set' (новая или бан): считаем от сегодня
            new_date = today + datetime.timedelta(days=days)

        # Сохраняем (Upsert)
        cur.execute("""
            INSERT INTO licenses (hwid, expiry_date) VALUES (%s, %s)
            ON CONFLICT (hwid) DO UPDATE SET expiry_date = EXCLUDED.expiry_date
        """, (hwid, new_date))
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "hwid": hwid, "date": str(new_date)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 3. ПОЛУЧИТЬ ВЕСЬ СПИСОК ===
@app.route('/list', methods=['POST'])
def get_all_licenses():
    data = request.json or {}
    if data.get('secret') != API_SECRET:
        return jsonify({"error": "Forbidden"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT hwid, expiry_date FROM licenses ORDER BY expiry_date DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Формируем список
        licenses_list = [{"hwid": r[0], "date": str(r[1])} for r in rows]
        
        return jsonify({"status": "success", "licenses": licenses_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
