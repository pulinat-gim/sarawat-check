DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS members;

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    nickname TEXT NOT NULL,
    class_room TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'สมาชิก',ห
    password_hash TEXT DEFAULT 'default_hash',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    check_date TEXT NOT NULL,
    status TEXT NOT NULL,
    check_time TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE,
    UNIQUE(member_id, check_date)
);