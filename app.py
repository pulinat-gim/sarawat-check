from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify
import sqlite3
import math

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ================== พิกัดจริงโรงเรียนพุทธชินราชพิทยา ==================
TARGET_NAME = "โรงเรียนพุทธชินราชพิทยา"
TARGET_LAT = 16.823345
TARGET_LNG = 100.266813
ALLOWED_RADIUS_M = 500      # รัศมีที่อนุญาต (500 เมตร)
MAX_GPS_ACCURACY_M = 1000   # ความแม่นยำ GPS สูงสุดที่ยอมรับ
# ===================================================================


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


def calculate_distance_m(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_member(cursor, keyword):
    cursor.execute("SELECT * FROM members WHERE id = ? OR nickname = ? OR full_name = ?",
                   (keyword, keyword, keyword))
    member = cursor.fetchone()
    if not member:
        cursor.execute("SELECT * FROM members WHERE nickname LIKE ? OR full_name LIKE ?",
                       (f"%{keyword}%", f"%{keyword}%"))
        member = cursor.fetchone()
    return member


@app.route('/')
def index():
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def api_config():
    return jsonify({
        'target_name': TARGET_NAME,
        'target_lat': TARGET_LAT,
        'target_lng': TARGET_LNG,
        'radius_m': ALLOWED_RADIUS_M
    })


@app.route('/api/members', methods=['GET'])
def api_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members ORDER BY id ASC")
    members = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(members)


@app.route('/api/action/checkin', methods=['POST'])
def api_action_checkin():
    data = request.get_json() or {}
    keyword = str(data.get('keyword', '')).strip()

    if not keyword:
        return jsonify({'ok': False, 'message': 'กรุณากรอกชื่อก่อนเช็กชื่อ'})

    try:
        user_lat = float(data.get('lat'))
        user_lng = float(data.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'message': '❌ ไม่ได้รับพิกัด GPS กรุณาเปิด GPS และอนุญาตตำแหน่ง'})

    try:
        accuracy = float(data.get('accuracy') or 0)
    except (TypeError, ValueError):
        accuracy = 0

    if accuracy > MAX_GPS_ACCURACY_M:
        return jsonify({'ok': False, 'message': '❌ สัญญาณ GPS ไม่แม่นยำ กรุณาลองใหม่อีกครั้ง'})

    distance_m = int(calculate_distance_m(TARGET_LAT, TARGET_LNG, user_lat, user_lng))

    if distance_m > ALLOWED_RADIUS_M:
        return jsonify({'ok': False, 'message': f'❌ เช็กชื่อไม่สำเร็จ: คุณอยู่ห่างจากพื้นที่เป้าหมาย ({distance_m:,} เมตร)'})

    conn = get_db_connection()
    cursor = conn.cursor()
    member = find_member(cursor, keyword)

    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})

    now_thai = datetime.now(ZoneInfo("Asia/Bangkok"))
    today_str = now_thai.strftime('%Y-%m-%d')
    time_str = now_thai.strftime('%H:%M')

    cursor.execute('''
        INSERT INTO attendance (member_id, date, status, time_recorded)
        VALUES (?, ?, 'มา', ?)
        ON CONFLICT(member_id, date) DO UPDATE SET status = 'มา', time_recorded = ?
    ''', (member['id'], today_str, time_str, time_str))

    conn.commit()
    conn.close()

    return jsonify({'ok': True, 'message': f'✅ บันทึก "มา" สำเร็จ: {member["full_name"]} ({time_str} น.)'})


@app.route('/api/action/leave', methods=['POST'])
def api_action_leave():
    data = request.get_json() or {}
    keyword = str(data.get('keyword', '')).strip()
    start_date_str = str(data.get('startDate', '')).strip()
    end_date_str = str(data.get('endDate', '')).strip() or start_date_str
    note = str(data.get('note', '')).strip()

    if not keyword or not start_date_str or not note:
        return jsonify({'ok': False, 'message': 'กรุณากรอกข้อมูลการลาให้ครบถ้วน'})

    conn = get_db_connection()
    cursor = conn.cursor()
    member = find_member(cursor, keyword)

    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})

    current_time_str = datetime.now(ZoneInfo("Asia/Bangkok")).strftime('%H:%M')

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        conn.close()
        return jsonify({'ok': False, 'message': '❌ รูปแบบวันที่ไม่ถูกต้อง'})

    if start_date > end_date:
        conn.close()
        return jsonify({'ok': False, 'message': '❌ วันที่เริ่มต้นต้องไม่มากกว่าวันสิ้นสุด'})

    current_date = start_date
    count = 0
    while current_date <= end_date:
        d_str = current_date.strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO attendance (member_id, date, status, note, time_recorded)
            VALUES (?, ?, 'ลา', ?, ?)
            ON CONFLICT(member_id, date) DO UPDATE SET status = 'ลา', note = ?, time_recorded = ?
        ''', (member['id'], d_str, note, current_time_str, note, current_time_str))
        count += 1
        current_date += timedelta(days=1)

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'message': f'✅ บันทึกการลาของ {member["full_name"]} รวม {count} วัน'})


@app.route('/api/attendance/today', methods=['GET'])
def api_attendance_today():
    today_date = datetime.now(ZoneInfo("Asia/Bangkok")).strftime('%Y-%m-%d')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members ORDER BY id ASC")
    members = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT member_id, date, status, time_recorded FROM attendance ORDER BY date DESC, id DESC")
    history_by_member = {}
    for row in cursor.fetchall():
        logs = history_by_member.setdefault(row['member_id'], [])
        if len(logs) < 30:
            logs.append({'date': row['date'], 'status': row['status'], 'time': row['time_recorded'] or '-'})

    cursor.execute("SELECT * FROM attendance WHERE date = ? ORDER BY id DESC", (today_date,))
    attendance_rows = cursor.fetchall()
    conn.close()

    attendance_records = {}
    activity_list = []
    for row in attendance_rows:
        mid = row['member_id']
        time_str = row['time_recorded'] or '-'
        if mid not in attendance_records:
            attendance_records[mid] = {'status': row['status'], 'note': row['note'] or ''}
        info = next((m for m in members if m['id'] == mid), None)
        if info:
            activity_list.append({
                'full_name': info['full_name'],
                'nickname': info['nickname'],
                'class_room': info['class_room'],
                'status': row['status'],
                'time': time_str if time_str != '-' else 'ลาล่วงหน้า'
            })

    stats = {'total': len(members), 'มา': 0, 'มาสาย': 0, 'ลา': 0, 'ยังไม่มา': 0}
    priority = {'มา': 3, 'มาสาย': 2, 'ลา': 1, 'ยังไม่มา': 0}
    attendance_list = []

    for m in members:
        rec = attendance_records.get(m['id'])
        status = rec['status'] if rec else 'ยังไม่มา'
        note = rec['note'] if rec else ''
        stats[status] = stats.get(status, 0) + 1
        attendance_list.append({
            'id': m['id'],
            'full_name': m['full_name'],
            'nickname': m['nickname'],
            'class_room': m['class_room'],
            'role': m['role'],
            'status': status,
            'note': note,
            'sort_priority': priority.get(status, 0),
            'history_logs': history_by_member.get(m['id'], [])
        })

    attendance_list.sort(key=lambda x: x['sort_priority'], reverse=True)

    return jsonify({'ok': True, 'stats': stats, 'attendance': attendance_list, 'activities': activity_list[:5]})


# เพิ่ม Route รองรับปุ่มรีเซ็ตสถานะหรืออัปเดตรายบุคคลจากหน้า Dashboard
@app.route('/api/action/reset', methods=['POST'])
def api_action_reset():
    data = request.get_json() or {}
    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'ok': False, 'message': 'ไม่พบรหัสสมาชิก'})
    
    today_date = datetime.now(ZoneInfo("Asia/Bangkok")).strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE member_id = ? AND date = ?", (member_id, today_date))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'message': 'รีเซ็ตสถานะเรียบร้อยแล้ว'})


if __name__ == '__main__':
    app.run(debug=True)