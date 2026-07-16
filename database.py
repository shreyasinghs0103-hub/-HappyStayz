import sys
import os

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)
import sqlite3
import csv
import random
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = "instance/happystayz.db"

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Ananya", "Diya",
               "Saanvi", "Myra", "Riya", "Arjun", "Rohan", "Neha", "Priya", "Karan"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Yadav", "Mishra", "Nair",
              "Reddy", "Kapoor", "Malhotra", "Chatterjee", "Iyer"]

STAFF_ROLES = [
    ("Front Desk", "Front Desk Executive", 22000),
    ("Front Desk", "Front Desk Executive", 22000),
    ("Housekeeping", "Housekeeping Staff", 16000),
    ("Housekeeping", "Housekeeping Staff", 16000),
    ("Housekeeping", "Housekeeping Supervisor", 24000),
    ("Kitchen", "Chef", 30000),
    ("Kitchen", "Kitchen Assistant", 15000),
    ("Maintenance", "Maintenance Technician", 20000),
    ("Security", "Security Guard", 18000),
    ("Management", "Duty Manager", 40000),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset=False):
    import os
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(DB_PATH):
        return  # already initialized

    random.seed(7)  # deterministic demo data (consistent usernames every fresh install)

    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE NOT NULL,
        room_type TEXT NOT NULL,
        price_per_night REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'available' -- available, occupied, maintenance
    );

    CREATE TABLE bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL,
        guest_name TEXT NOT NULL,
        guest_email TEXT,
        guest_phone TEXT,
        room_id INTEGER REFERENCES rooms(id),
        room_type_requested TEXT,
        check_in_date TEXT NOT NULL,
        check_out_date TEXT NOT NULL,
        adults INTEGER DEFAULT 1,
        children INTEGER DEFAULT 0,
        adr REAL,
        total_amount REAL,
        market_segment TEXT,
        country TEXT,
        status TEXT NOT NULL DEFAULT 'confirmed', -- confirmed, checked_in, checked_out, canceled, no_show
        checkin_code TEXT,
        checked_in_at TEXT,
        checked_out_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        role TEXT NOT NULL,
        monthly_salary REAL NOT NULL,
        hourly_rate REAL NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        bank_account TEXT NOT NULL,
        autopay_enabled INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        work_date TEXT NOT NULL,
        check_in_time TEXT,
        check_out_time TEXT,
        hours_worked REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'present', -- present, late, absent, half_day
        method TEXT DEFAULT 'self',  -- self, admin
        UNIQUE(staff_id, work_date)
    );

    CREATE TABLE payroll (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        period_month TEXT NOT NULL,  -- e.g. '2026-07'
        days_present INTEGER DEFAULT 0,
        total_hours REAL DEFAULT 0,
        gross_amount REAL DEFAULT 0,
        deductions REAL DEFAULT 0,
        net_amount REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending', -- pending, paid, failed
        paid_at TEXT,
        transaction_ref TEXT,
        UNIQUE(staff_id, period_month)
    );

    CREATE TABLE admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL
    );
    """)

    # --- Seed rooms ---
    room_types = [("Standard", 3200), ("Deluxe", 4800), ("Executive Suite", 7200),
                  ("Family Room", 5600), ("Presidential Suite", 12500)]
    room_id = 1
    for floor in range(1, 6):
        for pos in range(1, 9):
            rtype, price = room_types[(floor - 1) % len(room_types)]
            room_num = f"{floor}{pos:02d}"
            c.execute(
                "INSERT INTO rooms (room_number, room_type, price_per_night, status) VALUES (?,?,?,?)",
                (room_num, rtype, price, "available")
            )
            room_id += 1
    conn.commit()

    # --- Seed staff ---
    for idx, (dept, role, salary) in enumerate(STAFF_ROLES, start=1):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        name = f"{fname} {lname}"
        staff_code = f"HSZ-{idx:03d}"
        username = f"{fname.lower()}{idx}"
        hourly_rate = round(salary / (30 * 8), 2)
        c.execute("""INSERT INTO staff
            (staff_code, name, department, role, monthly_salary, hourly_rate,
             username, password_hash, bank_account, autopay_enabled, active)
            VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
            (staff_code, name, dept, role, salary, hourly_rate,
             username, generate_password_hash("staff123"),
             f"XXXXXXXX{1000+idx}", 1))
    conn.commit()

    # --- Seed admin ---
    c.execute("INSERT INTO admin_users (username, password_hash, name) VALUES (?,?,?)",
               ("admin", generate_password_hash("admin123"), "Hotel Admin"))
    conn.commit()

    # --- Seed bookings from Kaggle-style CSV ---
    rooms = c.execute("SELECT id, room_type, price_per_night FROM rooms").fetchall()
    rooms_by_type = {}
    for r in rooms:
        rooms_by_type.setdefault(r["room_type"], []).append(r)

    type_map = {"A": "Standard", "B": "Deluxe", "C": "Executive Suite",
                "D": "Family Room", "E": "Presidential Suite"}

    csv_path = get_resource_path("data/hotel_bookings.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if count >= 60:  # seed a manageable number of live bookings
                break
            if row["is_canceled"] == "1":
                continue
            room_type = type_map.get(row["reserved_room_type"], "Standard")
            candidates = rooms_by_type.get(room_type, rooms)
            room = random.choice(candidates)
            nights = int(row["stays_in_weekend_nights"]) + int(row["stays_in_week_nights"])
            nights = max(nights, 1)
            checkin = date.today() + timedelta(days=random.randint(-5, 10))
            checkout = checkin + timedelta(days=nights)
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            guest_name = f"{fname} {lname}"
            booking_code = f"HSZ{100000 + count}"
            adr = float(row["adr"])
            total = round(adr * nights, 2)
            status = "confirmed"
            c.execute("""INSERT INTO bookings
                (booking_code, guest_name, guest_email, guest_phone, room_id,
                 room_type_requested, check_in_date, check_out_date, adults, children,
                 adr, total_amount, market_segment, country, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (booking_code, guest_name, f"{fname.lower()}.{lname.lower()}@email.com",
                 f"9{random.randint(100000000,999999999)}", room["id"], room_type,
                 checkin.isoformat(), checkout.isoformat(),
                 int(row["adults"]), int(row["children"] or 0),
                 adr, total, row["market_segment"], row["country"], status))
            count += 1
    conn.commit()

    # --- Seed 30 days of attendance history for each staff member ---
    staff_rows = c.execute("SELECT id, hourly_rate FROM staff").fetchall()
    today = date.today()
    for s in staff_rows:
        for d in range(30, 0, -1):
            work_date = today - timedelta(days=d)
            if work_date.weekday() == 6:  # skip Sundays
                continue
            roll = random.random()
            if roll < 0.05:
                status, hours = "absent", 0
                check_in, check_out = None, None
            else:
                check_in_hour = 9 if roll > 0.15 else 10
                status = "present" if check_in_hour == 9 else "late"
                hours = round(random.uniform(7.5, 9), 2)
                check_in = f"{work_date.isoformat()} {check_in_hour:02d}:0{random.randint(0,5)}:00"
                check_out_hour = check_in_hour + int(hours)
                check_out = f"{work_date.isoformat()} {check_out_hour:02d}:{random.randint(10,50)}:00"
            c.execute("""INSERT OR IGNORE INTO attendance
                (staff_id, work_date, check_in_time, check_out_time, hours_worked, status, method)
                VALUES (?,?,?,?,?,?, 'self')""",
                (s["id"], work_date.isoformat(), check_in, check_out, hours, status))
    conn.commit()
    conn.close()
    print("Database initialized and seeded.")


if __name__ == "__main__":
    init_db(reset=True)
