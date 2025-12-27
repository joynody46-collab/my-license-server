import os
import datetime
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Получаем настройки из "сейфа" (переменных окружения)
DATABASE_URL = os.environ.get("DATABASE_URL")
API_SECRET = os.environ.get("API_SECRET")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def home():
    return "Сервер лицензий работает!"

# Эту ссылку вы вставите в скрипт (проверка лицензии)
@app.route('/check', methods=['POST'])
def check():
    data = request.json
    hwid = data.get('hwid')
    
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
        return jsonify({"error": str(e)})

# Эту ссылку вы вставите в ТГ-бота (выдача лицензии)
@app.route('/add', methods=['POST'])
def add_license():
    data = request.json
    if data.get('secret') != API_SECRET:
        return jsonify({"error": "Wrong secret"}), 403

    hwid = data.get('hwid')
    days = int(data.get('days', 30))
    new_date = datetime.date.today() + datetime.timedelta(days=days)

    conn = get_db_connection()
    cur = conn.cursor()
    # Создаем таблицу, если её нет (автоматически при первом запуске)
    cur.execute("CREATE TABLE IF NOT EXISTS licenses (hwid TEXT PRIMARY KEY, expiry_date DATE)")
    # Добавляем или обновляем лицензию
    cur.execute("""
        INSERT INTO licenses (hwid, expiry_date) VALUES (%s, %s)
        ON CONFLICT (hwid) DO UPDATE SET expiry_date = EXCLUDED.expiry_date
    """, (hwid, new_date))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "success", "hwid": hwid, "date": str(new_date)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)