import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# ลบเฉพาะประวัติการเช็กชื่อ/การลาทั้งหมด
cursor.execute("DELETE FROM attendance")
conn.commit()
conn.close()

print("🧹 ล้างประวัติการทดสอบเรียบร้อยแล้ว!")