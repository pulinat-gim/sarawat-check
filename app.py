from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def find_member_by_keyword(cursor, keyword):
    keyword = keyword.strip()
    
    # 1. ค้นหาแบบตรงเป๊ะก่อน (Exact match) กับ id, nickname หรือ full_name เพื่อป้องกันพิมพ์ "กร" แล้วไปโดน "ณฐกร"
    cursor.execute("SELECT * FROM members WHERE id = ? OR nickname = ? OR full_name = ?", 
                   (keyword, keyword, keyword))
    member = cursor.fetchone()
    if member:
        return member
        
    # 2. ถ้าไม่เจอแบบตรงเป๊ะ ค่อยหาแบบ Substring (LIKE)
    cursor.execute("SELECT * FROM members WHERE nickname LIKE ? OR full_name LIKE ?", 
                   (f"%{keyword}%", f"%{keyword}%"))
    return cursor.fetchone()

# หน้าแรกสุด (/) คือหน้าเช็กชื่อ (login.html)
@app.route('/')
def index():
    return render_template('login.html')

# หน้าแดชบอร์ดสรุปผล (index.html) - เข้าได้ทันทีไม่ต้องใส่รหัส
@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/api/members', methods=['GET'])
def api_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members ORDER BY id ASC")
    members = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(members)

# API เช็กชื่อ (ไม่บล็อก GPS และแก้ปัญหาค้นหาชื่อแม่นยำขึ้น)
@app.route('/api/action/checkin', methods=['POST'])
def api_action_checkin():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    
    if not keyword:
        return jsonify({'ok': False, 'message': 'กรุณากรอกรหัสหรือชื่อ'})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    member = find_member_by_keyword(cursor, keyword)
    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})
        
    member_id = member['id']
    now_thai = datetime.now(ZoneInfo("Asia/Bangkok"))
    today_str = now_thai.strftime('%Y-%m-%d')
    time_str = now_thai.strftime('%H:%M')
    
    cursor.execute('''
        INSERT INTO attendance (member_id, date, status, time_recorded)
        VALUES (?, ?, 'มา', ?)
        ON CONFLICT(member_id, date) DO UPDATE SET status = 'มา', time_recorded = ?
    ''', (member_id, today_str, time_str, time_str))
    
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'message': f'✅ บันทึก "มา" สำเร็จ: {member["full_name"]} ({time_str} น.)'})

# API แจ้งลาล่วงหน้า (รองรับหลายวัน และแก้ปัญหาค้นหาชื่อ)
@app.route('/api/action/leave', methods=['POST'])
def api_action_leave():
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    start_date_str = data.get('startDate', '').strip()
    end_date_str = data.get('endDate', '').strip()
    note = data.get('note', '').strip()
    
    if not keyword:
        return jsonify({'ok': False, 'message': 'กรุณากรอกรหัสหรือชื่อ'})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    member = find_member_by_keyword(cursor, keyword)
    if not member:
        conn.close()
        return jsonify({'ok': False, 'message': f'ไม่พบรายชื่อ "{keyword}" ในระบบ'})
        
    member_id = member['id']
    now_thai = datetime.now(ZoneInfo("Asia/Bangkok"))
    current_time_str = now_thai.strftime('%H:%M')
    
    if not end_date_str:
        end_date_str = start_date_str
        
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        if start_date > end_date:
            conn.close()
            return jsonify({'ok': False, 'message': '❌ วันที่เริ่มต้นต้องไม่มากกว่าวันสิ้นสุด'})
            
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
        return jsonify({'ok': True, 'message': f'✅ บันทึกการลาของ {member["full_name"]} รวม {count} วัน'})
        
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'message': '❌ รูปแบบวันที่ไม่ถูกต้อง'})

@app.route('/api/attendance/today', methods=['GET'])
def api_attendance_today():
    now_thai = datetime.now(ZoneInfo("Asia/Bangkok"))
    today_date = now_thai.strftime('%Y-%m-%d')
    
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
            attendance_records[mid] = {'status': row['status'], 'note': row['note'] or '', 'time': time_str}
            
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
    
    priority = {'มา': 3, 'มาสาย': 2, 'ลา': 1, 'ยังไม่มา': 0}
    
    for m in members:
        rec = attendance_records.get(m['id'])
        m_logs = history_by_member.get(m['id'], [])
        
        if rec:
            status = rec['status']
            note = rec['note'] or ''
            sort_priority = priority.get(status, 0)
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