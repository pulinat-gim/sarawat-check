from flask import Flask, render_template, request, jsonify
import sqlite3
import math
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sarawat_check_secret_key'

DB_PATH = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('index.html')

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_member_by_keyword(cursor, keyword):
    cursor.execute("SELECT * FROM members WHERE nickname = ? OR full_name = ?", (keyword, keyword))
    member = cursor.fetchone()
    if member:
        return member
    cursor.execute("SELECT * FROM members WHERE nickname LIKE ? OR full_name LIKE ?", (f'{keyword}%', f'% {keyword}%'))
    member = cursor.fetchone()
    if member:
        return member
    cursor.execute("SELECT * FROM members WHERE nickname LIKE ? OR full_name LIKE ?", (f'%{keyword}%', f'%{keyword}%'))
    return cursor.fetchone()

@app.route('/api/action/checkin', methods=['POST'])
def api_action_checkin():
    data = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    lat = data.get('lat')
    lng = data.get('lng')
    
    if not keyword:
        return jsonify({'ok': False, 'message': 'กรุณาพิมพ์ชื่อสมาชิก'})
    
    SCHOOL_LAT = 16.82322
    SCHOOL_LNG = 100.26615
    ALLOW_RADIUS_METERS = 400  
    
    if lat is not None and lng is not None:
        distance = calculate_distance(lat, lng, SCHOOL_LAT, SCHOOL_LNG)
        if distance > ALLOW_RADIUS_METERS:
            return jsonify({'ok': False, 'message': f'❌ เช็กชื่อไม่สำเร็จ: คุณอยู่นอกพื้นที่โรงเรียน (ห่างจากโรงเรียนประมาณ {int(distance)} เมตร)'})
    else:
        return jsonify({'ok': False, 'message': '❌ ไม่สามารถตรวจสอบพิกัด GPS ได้ กรุณาเปิดใช้งาน Location'})

    conn = get_db_connection()
    cursor = conn.cursor()
    
    member = find_member_by_keyword(cursor, keyword)
    
    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})
    
    member_id = member['id']
    now = datetime.now()
    today_date = now.strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M')
    
    status = 'มาสาย' if current_time_str > '07:40' else 'มา'
    
    cursor.execute('''
        INSERT INTO attendance (member_id, date, status, note, lat, lng, time_recorded) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(member_id, date) DO UPDATE SET status = ?, note = 'เช็กชื่อปกติ', lat = ?, lng = ?, time_recorded = ?
    ''', (member_id, today_date, status, 'เช็กชื่อปกติ', lat, lng, current_time_str, status, lat, lng, current_time_str))
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'message': f'✅ เช็กชื่อสำเร็จ: {member["full_name"]} ({member["nickname"]}) - เวลา {current_time_str} น.'})

@app.route('/api/action/leave', methods=['POST'])
def api_action_leave():
    data = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    note = data.get('note', '').strip()
    start_date_str = data.get('startDate', '').strip()
    end_date_str = data.get('endDate', '').strip()
    
    if not keyword or not note or not start_date_str:
        return jsonify({'ok': False, 'message': 'กรุณากรอกชื่อ วันที่เริ่มต้น และเหตุผลการลา'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    member = find_member_by_keyword(cursor, keyword)
        
    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})
    
    member_id = member['id']
    current_time_str = datetime.now().strftime('%H:%M')
    
    # ถ้าไม่ได้ระบุวันสิ้นสุด ให้ใช้วันเริ่มต้นวันเดียว
    if not end_date_str:
        end_date_str = start_date_str

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        if start_date > end_date:
            conn.close()
            return jsonify({'ok': False, 'message': '❌ วันที่เริ่มต้นต้องไม่มากกว่าวันสิ้นสุด'})

        # วนลูปบันทึกการลาทีละวันในช่วงที่เลือก
        delta = timedelta(days=1)
        current_date = start_date
        count = 0

        while current_date <= end_date:
            d_str = current_date.strftime('%Y-%m-%d')
            cursor.execute('''
                INSERT INTO attendance (member_id, date, status, note, time_recorded) 
                VALUES (?, ?, 'ลา', ?, ?)
                ON CONFLICT(member_id, date) DO UPDATE SET status = 'ลา', note = ?, time_recorded = ?
            ''', (member_id, d_str, note, current_time_str, note, current_time_str))
            count += 1
            current_date += delta

        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'message': f'✅ บันทึกการลาของ {member["full_name"]} รวม {count} วัน สำเร็จ!'})

    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'message': '❌ รูปแบบวันที่ไม่ถูกต้อง'})

@app.route('/api/attendance/today', methods=['GET'])
def api_attendance_today():
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM members ORDER BY id ASC")
    members = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT member_id, date, status, time_recorded 
        FROM attendance 
        ORDER BY date DESC, id DESC
    ''')
    history_rows = cursor.fetchall()
    
    history_by_member = {}
    for row in history_rows:
        mid = row['member_id']
        if mid not in history_by_member:
            history_by_member[mid] = []
        if len(history_by_member[mid]) < 30:
            history_by_member[mid].append({
                'date': row['date'],
                'status': row['status'],
                'time': row['time_recorded'] or '-'
            })

    cursor.execute("SELECT * FROM attendance WHERE date = ? ORDER BY id DESC", (today_date,))
    attendance_rows = cursor.fetchall()
    
    attendance_records = {}
    activity_list = []
    
    for row in attendance_rows:
        mid = row['member_id']
        time_str = row['time_recorded'] if 'time_recorded' in row.keys() and row['time_recorded'] else '-'
        
        if mid not in attendance_records:
            attendance_records[mid] = {'status': row['status'], 'note': row['note'], 'time': time_str, 'id_order': row['id']}
        
        member_info = next((m for m in members if m['id'] == mid), None)
        if member_info:
            activity_list.append({
                'full_name': member_info['full_name'],
                'nickname': member_info['nickname'],
                'class_room': member_info['class_room'],
                'status': row['status'],
                'time': time_str if time_str != '-' else 'ลาล่วงหน้า'
            })

    conn.close()
    
    attendance_list = []
    stats = {'total': len(members), 'มา': 0, 'มาสาย': 0, 'ลา': 0, 'ยังไม่มา': 0}
    
    for m in members:
        rec = attendance_records.get(m['id'])
        m_logs = history_by_member.get(m['id'], [])
        
        if rec:
            status = rec['status']
            note = rec['note'] or ''
            sort_priority = rec['id_order'] 
        else:
            status = 'ยังไม่มา'
            note = ''
            sort_priority = 0
            
        stats[status] += 1
        attendance_list.append({
            'id': m['id'],
            'full_name': m['full_name'],
            'nickname': m['nickname'],
            'class_room': m['class_room'],
            'role': m['role'],
            'status': status,
            'note': note,
            'sort_priority': sort_priority,
            'history_logs': m_logs
        })
        
    attendance_list.sort(key=lambda x: x['sort_priority'], reverse=True)
        
    return jsonify({
        'ok': True, 
        'stats': stats, 
        'attendance': attendance_list, 
        'activities': activity_list[:5]
    })

if __name__ == '__main__':
    app.run(debug=True) 