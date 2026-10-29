document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('login-form')) {
        const loginForm = document.getElementById('login-form');
        loginForm.onsubmit = handleLoginAndCheckin;
    }
    
    if (document.getElementById('member-container')) {
        loadDashboardData('all');
        loadCurrentUser();
    }
});

// จัดการหน้า Login และเช็กชื่ออัตโนมัติทันที
async function handleLoginAndCheckin(event) {
    event.preventDefault();
    const keyword = document.getElementById('member-search-input').value.trim();
    let errorDiv = document.getElementById('error-message');
    
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'error-message';
        errorDiv.style.cssText = 'color: #dc3545; margin-top: 15px; font-size: 0.9em; font-weight: bold;';
        document.getElementById('login-form').appendChild(errorDiv);
    }
    errorDiv.innerText = '';

    try {
        const res = await fetch(`/api/members?search=${encodeURIComponent(keyword)}`);
        const data = await res.json();

        if (data.ok && data.members.length > 0) {
            const matchedMember = data.members[0];
            
            const selectRes = await fetch('/api/select_user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ member_id: matchedMember.id })
            });
            const selectResult = await selectRes.json();
            
            if (!selectResult.ok) {
                errorDiv.innerText = 'ไม่สามารถเข้าสู่ระบบได้';
                return;
            }

            const checkinRes = await fetch('/api/checkin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const checkinResult = await checkinRes.json();

            if (checkinResult.ok) {
                window.location.href = '/dashboard';
            } else {
                errorDiv.innerText = 'เกิดข้อผิดพลาดในการเช็กชื่อ';
            }
        } else {
            errorDiv.innerText = 'ไม่พบชื่อนี้ในระบบ กรุณาตรวจสอบใหม่อีกครั้ง';
        }
    } catch (err) {
        console.error('Login error:', err);
        errorDiv.innerText = 'เกิดข้อผิดพลาดในการเชื่อมต่อระบบ';
    }
}

// โหลดข้อมูล Dashboard และแสดงรายชื่อตามที่คลิก
async function loadDashboardData(filterStatus = 'all') {
    try {
        const res = await fetch('/api/attendance/today');
        const data = await res.json();
        if (!data.ok) return;

        // อัปเดตตัวเลขสถิติบนการ์ด
        document.getElementById('stat-total').innerText = data.stats.total;
        document.getElementById('stat-present').innerText = data.stats.มา;
        document.getElementById('stat-late').innerText = data.stats.มาสาย;
        document.getElementById('stat-absent').innerText = data.stats.ยังไม่มา;

        const container = document.getElementById('member-container');
        if (!container) return;
        
        container.innerHTML = '';

        // กรองรายชื่อตามสถานะที่เลือก
        const filteredList = data.attendance.filter(m => {
            if (filterStatus === 'all') return true;
            return m.status === filterStatus;
        });

        if (filteredList.length === 0) {
            container.innerHTML = `<p style="text-align: center; color: #888; padding: 20px;">ไม่พบรายชื่อในกลุ่มนี้</p>`;
            return;
        }

        // แสดงรายชื่อ
        filteredList.forEach(m => {
            const item = document.createElement('div');
            item.className = 'member-item';
            item.style.cssText = 'padding: 12px 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;';
            item.innerHTML = `
                <div>
                    <strong>${m.full_name} (${m.nickname})</strong><br>
                    <span style="font-size: 0.85em; color: #666;">ห้อง ${m.class_room} | ตำแหน่ง: ${m.role}</span>
                </div>
                <div>
                    <span style="padding: 5px 10px; border-radius: 4px; color: white; font-weight: bold; font-size: 0.9em; background: ${m.status === 'มา' ? '#28a745' : m.status === 'มาสาย' ? '#ffc107' : '#dc3545'}">${m.status}</span>
                </div>
            `;
            container.appendChild(item);
        });
    } catch (err) {
        console.error('Error loading dashboard data:', err);
    }
}

// โหลดข้อมูลผู้ใช้ปัจจุบัน
async function loadCurrentUser() {
    try {
        const res = await fetch('/api/current_user');
        const data = await res.json();
        const container = document.getElementById('checkin-panel-content');
        if (!container) return;

        if (data.ok && data.member) {
            const m = data.member;
            container.innerHTML = `
                <div style="margin-bottom: 5px;">
                    <strong>ผู้ใช้งานปัจจุบัน: ${m.full_name} (${m.nickname})</strong><br>
                    <span style="font-size: 0.9em; color: #555;">ห้อง ${m.class_room} | ตำแหน่ง: ${m.role}</span><br>
                    <span style="font-size: 0.9em; color: #28a745; font-weight: bold;">สถานะวันนี้: ${m.today_status || 'บันทึกเรียบร้อย'}</span>
                </div>
            `;
        } else {
            container.innerHTML = `<p style="color: #dc3545; margin: 0;">ยังไม่ได้เลือกตัวตน <a href="/">กลับไปหน้าเลือกชื่อ</a></p>`;
        }
    } catch (err) {
        console.error('Error loading current user:', err);
    }
}