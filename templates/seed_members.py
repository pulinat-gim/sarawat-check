import sqlite3
from werkzeug.security import generate_password_hash

def seed_database():
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()

    # รายชื่อสมาชิกเก่าทั้งหมด (สามารถเพิ่มหรือแก้ไขตรงนี้ได้เลยครับ)
    members_data = [
        {"code": "66001", "name": "นางสาวพิมรภัทร แบนคล้าย", "nickname": "ไอซ์", "room": "ม.5/1"},
        {"code": "66002", "name": "นายธีรเดช ไพศาลพิสุทธิ์", "nickname": "เนส", "room": "ม.5/1"},
        {"code": "66003", "name": "นางสาวธนวรรณ แบนคล้าย", "nickname": "โรส", "room": "ม.5/2"},
        {"code": "66004", "name": "นางสาวชยุดรา ชมป้อม", "nickname": "น้ำเพรช", "room": "ม.5/2"},
        {"code": "66005", "name": "นายฐิติวัตน์ สีสวย", "nickname": "โชค", "room": "ม.5/2"},
        {"code": "66006", "name": "นายณฐกร เส็งสิน", "nickname": "เบลเยี่ยม", "room": "ม.5/2"},
        {"code": "66007", "name": "นางสาวฐิติรัตน์ พนัสขาว", "nickname": "อาย", "room": "ม.5/3"},
        {"code": "66008", "name": "นางสาวชญานิษฐ์ พรหมเกิด", "nickname": "เอย", "room": "ม.5/3"}
    ]

    default_password_hash = generate_password_hash("1234")

    for m in members_data:
        cursor.execute("""
            INSERT INTO members (student_code, full_name, nickname, class_room, role, password_hash, is_active)
            VALUES (?, ?, ?, ?, 'member', ?, 1)
        """, (m["code"], m["name"], m["nickname"], m["room"], default_password_hash))

    conn.commit()
    conn.close()
    print("เพิ่มข้อมูลสมาชิกเก่าทั้งหมดสำเร็จ!")

if __name__ == '__main__':
    seed_database()