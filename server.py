import os
import datetime
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
API_SECRET = os.environ.get("API_SECRET")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def home():
    return "License Server Updated!"

# Проверка лицензии (без изменений)
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

# Выдача/Продление лицензии (ОБНОВЛЕНО)
@app.route('/add', methods=['POST'])
def add_license():
    data = request.json
    if data.get('secret') != API_SECRET:
        return jsonify({"error": "Wrong secret"}), 403

    hwid = data.get('hwid')
    days = int(data.get('days', 30))
    mode = data.get('mode', 'set') # 'set' (с сегодня) или 'add' (продлить)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Сначала ищем, есть ли такая лицензия
    cur.execute("SELECT expiry_date FROM licenses WHERE hwid = %s", (hwid,))
    row = cur.fetchone()
    
    today = datetime.date.today()
    current_expiry = row[0] if row else today

    # 2. Логика расчета даты
    if mode == 'add':
        # Если лицензия уже просрочена, продлеваем от СЕГОДНЯ. 
        # Если активна, продлеваем от ДАТЫ ОКОНЧАНИЯ.
        start_date = max(current_expiry, today)
        new_date = start_date + datetime.timedelta(days=days)
    else:
        # Режим 'set' (или 'ban') - считаем от сегодня
        new_date = today + datetime.timedelta(days=days)

    # 3. Сохраняем
    cur.execute("""
        INSERT INTO licenses (hwid, expiry_date) VALUES (%s, %s)
        ON CONFLICT (hwid) DO UPDATE SET expiry_date = EXCLUDED.expiry_date
    """, (hwid, new_date))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"status": "success", "hwid": hwid, "date": str(new_date), "mode": mode})
# === НОВАЯ ФУНКЦИЯ: ПОЛУЧИТЬ ВЕСЬ СПИСОК ===
@app.route('/list', methods=['POST'])
def get_all_licenses():
    data = request.json
    # Обязательно проверяем пароль, чтобы базу не украли
    if data.get('secret') != API_SECRET:
        return jsonify({"error": "Forbidden"}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Запрашиваем HWID и Дату, сортируем по дате окончания
        cur.execute("SELECT hwid, expiry_date FROM licenses ORDER BY expiry_date ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Превращаем в красивый список
        licenses_list = [{"hwid": row[0], "date": str(row[1])} for row in rows]
        
        return jsonify({"status": "success", "licenses": licenses_list})
    except Exception as e:
        return jsonify({"error": str(e)})
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

