import os
import random
import string
import threading
import time
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash

from database import get_db, init_db, DB_PATH

app = Flask(__name__)
app.secret_key = "happystayz-dev-secret-key-change-me"

os.makedirs("instance", exist_ok=True)
init_db()


# ---------------------------------------------------------------- helpers
def gen_code(prefix, length=6):
    chars = string.ascii_uppercase + string.digits
    return prefix + "".join(random.choices(chars, k=length))


def current_month():
    return date.today().strftime("%Y-%m")


def run_payroll_for_month(period_month, conn=None):
    """Calculate & auto-disburse salary for every active staff member for
    the given YYYY-MM period, based on attendance records. This simulates
    an autopay job: once salary is computed it's marked 'paid' immediately
    for staff who have autopay enabled (like a real bank auto-debit)."""
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    c = conn.cursor()
    staff_list = c.execute("SELECT * FROM staff WHERE active = 1").fetchall()
    results = []
    for s in staff_list:
        existing = c.execute(
            "SELECT * FROM payroll WHERE staff_id=? AND period_month=?",
            (s["id"], period_month)).fetchone()
        if existing and existing["status"] == "paid":
            results.append(existing)
            continue

        rows = c.execute(
            "SELECT * FROM attendance WHERE staff_id=? AND work_date LIKE ?",
            (s["id"], f"{period_month}%")).fetchall()
        days_present = sum(1 for r in rows if r["status"] in ("present", "late", "half_day"))
        total_hours = sum(r["hours_worked"] or 0 for r in rows)
        gross = round(total_hours * s["hourly_rate"], 2)
        deductions = round(gross * 0.02, 2)  # flat 2% notional deduction (PF-like)
        net = round(gross - deductions, 2)
        status = "paid" if s["autopay_enabled"] else "pending"
        paid_at = datetime.now().isoformat(timespec="seconds") if s["autopay_enabled"] else None
        txn_ref = gen_code("TXN") if s["autopay_enabled"] else None

        if existing:
            c.execute("""UPDATE payroll SET days_present=?, total_hours=?, gross_amount=?,
                deductions=?, net_amount=?, status=?, paid_at=?, transaction_ref=?
                WHERE id=?""",
                (days_present, total_hours, gross, deductions, net, status,
                 paid_at, txn_ref, existing["id"]))
        else:
            c.execute("""INSERT INTO payroll (staff_id, period_month, days_present,
                total_hours, gross_amount, deductions, net_amount, status, paid_at, transaction_ref)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (s["id"], period_month, days_present, total_hours, gross,
                 deductions, net, status, paid_at, txn_ref))
        results.append({"staff": s["name"], "net": net, "status": status})
    conn.commit()
    if own_conn:
        conn.close()
    return results


def autopay_background_worker():
    """Runs in a background thread. Checks once a day whether it's the 1st
    of the month, and if so, auto-runs payroll for the previous month for
    every staff member with autopay enabled. This is the 'autopay saved'
    automatic salary disbursement feature."""
    last_run_month = None
    while True:
        today = date.today()
        if today.day == 1 and last_run_month != today.strftime("%Y-%m"):
            prev_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            try:
                run_payroll_for_month(prev_month)
                last_run_month = today.strftime("%Y-%m")
            except Exception as e:
                print("Autopay job error:", e)
        time.sleep(60 * 60)  # check hourly


# ---------------------------------------------------------------- public
@app.route("/")
def home():
    conn = get_db()
    
    available_rooms = conn.execute(
        "SELECT room_type, COUNT(*) as cnt, MIN(price_per_night) as price "
        "FROM rooms WHERE status='available' GROUP BY room_type").fetchall()
    conn.close()
    return render_template("index.html", room_types=available_rooms)


@app.route("/guest/checkin", methods=["GET", "POST"])
def guest_checkin():
    result = None
    if request.method == "POST":
        code = request.form.get("booking_code", "").strip().upper()
        conn = get_db()
        booking = conn.execute(
            "SELECT b.*, r.room_number, r.room_type FROM bookings b "
            "LEFT JOIN rooms r ON b.room_id = r.id WHERE b.booking_code = ?",
            (code,)).fetchone()
        if not booking:
            flash("No booking found with that code. Please check and try again.", "danger")
        elif booking["status"] == "checked_in":
            flash("This booking is already checked in.", "info")
        elif booking["status"] in ("canceled", "no_show"):
            flash("This booking cannot be checked in (canceled / no-show).", "danger")
        else:
            key_code = gen_code("KEY-", 5)
            conn.execute(
                "UPDATE bookings SET status='checked_in', checkin_code=?, checked_in_at=? WHERE id=?",
                (key_code, datetime.now().isoformat(timespec="seconds"), booking["id"]))
            conn.execute("UPDATE rooms SET status='occupied' WHERE id=?", (booking["room_id"],))
            conn.commit()
            result = {
                "guest_name": booking["guest_name"],
                "room_number": booking["room_number"],
                "room_type": booking["room_type"],
                "check_out_date": booking["check_out_date"],
                "key_code": key_code,
            }
        conn.close()
    return render_template("guest_checkin.html", result=result)


@app.route("/guest/book", methods=["GET", "POST"])
def guest_book():
    conn = get_db()
    room_types = conn.execute(
        "SELECT room_type, price_per_night FROM rooms GROUP BY room_type").fetchall()
    if request.method == "POST":
        name = request.form["guest_name"].strip()
        email = request.form.get("guest_email", "").strip()
        phone = request.form.get("guest_phone", "").strip()
        room_type = request.form["room_type"]
        checkin = request.form["check_in_date"]
        checkout = request.form["check_out_date"]
        adults = int(request.form.get("adults", 1))
        children = int(request.form.get("children", 0))

        room = conn.execute(
            "SELECT * FROM rooms WHERE room_type=? AND status='available' LIMIT 1",
            (room_type,)).fetchone()
        if not room:
            flash("Sorry, no rooms of that type are available right now.", "danger")
            conn.close()
            return redirect(url_for("guest_book"))

        nights = max((datetime.fromisoformat(checkout) - datetime.fromisoformat(checkin)).days, 1)
        total = round(room["price_per_night"] * nights, 2)
        code = gen_code("HSZ")
        conn.execute("""INSERT INTO bookings
            (booking_code, guest_name, guest_email, guest_phone, room_id, room_type_requested,
             check_in_date, check_out_date, adults, children, adr, total_amount, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'confirmed')""",
            (code, name, email, phone, room["id"], room_type, checkin, checkout,
             adults, children, room["price_per_night"], total))
        conn.commit()
        conn.close()
        flash(f"Booking confirmed! Your booking code is {code} — use it for self check-in.", "success")
        return redirect(url_for("guest_book"))
    conn.close()
    return render_template("guest_book.html", room_types=room_types)


# ---------------------------------------------------------------- staff
@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        staff = conn.execute("SELECT * FROM staff WHERE username=?", (username,)).fetchone()
        conn.close()
        if staff and check_password_hash(staff["password_hash"], password):
            session["staff_id"] = staff["id"]
            session["staff_name"] = staff["name"]
            return redirect(url_for("staff_dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("staff_login.html")


@app.route("/staff/logout")
def staff_logout():
    session.pop("staff_id", None)
    return redirect(url_for("home"))


@app.route("/staff/dashboard", methods=["GET", "POST"])
def staff_dashboard():
    if "staff_id" not in session:
        return redirect(url_for("staff_login"))
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff WHERE id=?", (session["staff_id"],)).fetchone()
    today = date.today().isoformat()

    if request.method == "POST":
        action = request.form.get("action")
        row = conn.execute(
            "SELECT * FROM attendance WHERE staff_id=? AND work_date=?",
            (staff["id"], today)).fetchone()
        now_str = datetime.now().isoformat(timespec="seconds")
        if action == "check_in":
            if row:
                flash("You've already checked in today.", "info")
            else:
                hour = datetime.now().hour
                status = "present" if hour < 10 else "late"
                conn.execute("""INSERT INTO attendance
                    (staff_id, work_date, check_in_time, status, method)
                    VALUES (?,?,?,?, 'self')""", (staff["id"], today, now_str, status))
                conn.commit()
                flash("Checked in successfully!", "success")
        elif action == "check_out":
            if not row or row["check_in_time"] is None:
                flash("You need to check in first.", "warning")
            elif row["check_out_time"]:
                flash("You've already checked out today.", "info")
            else:
                check_in_dt = datetime.fromisoformat(row["check_in_time"])
                hours = round((datetime.now() - check_in_dt).total_seconds() / 3600, 2)
                conn.execute("""UPDATE attendance SET check_out_time=?, hours_worked=?
                    WHERE id=?""", (now_str, hours, row["id"]))
                conn.commit()
                flash(f"Checked out. Hours worked today: {hours}", "success")
        conn.close()
        return redirect(url_for("staff_dashboard"))

    today_row = conn.execute(
        "SELECT * FROM attendance WHERE staff_id=? AND work_date=?",
        (staff["id"], today)).fetchone()
    history = conn.execute(
        "SELECT * FROM attendance WHERE staff_id=? ORDER BY work_date DESC LIMIT 14",
        (staff["id"],)).fetchall()
    payroll_history = conn.execute(
        "SELECT * FROM payroll WHERE staff_id=? ORDER BY period_month DESC LIMIT 6",
        (staff["id"],)).fetchall()
    conn.close()
    return render_template("staff_dashboard.html", staff=staff, today_row=today_row,
                           history=history, payroll_history=payroll_history, today=today)


# ---------------------------------------------------------------- admin
def admin_required():
    return "admin_id" in session


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        admin = conn.execute("SELECT * FROM admin_users WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("home"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    stats = {
        "total_rooms": conn.execute("SELECT COUNT(*) c FROM rooms").fetchone()["c"],
        "occupied_rooms": conn.execute("SELECT COUNT(*) c FROM rooms WHERE status='occupied'").fetchone()["c"],
        "total_bookings": conn.execute("SELECT COUNT(*) c FROM bookings").fetchone()["c"],
        "checked_in_today": conn.execute(
            "SELECT COUNT(*) c FROM bookings WHERE checked_in_at LIKE ?",
            (f"{date.today().isoformat()}%",)).fetchone()["c"],
        "total_staff": conn.execute("SELECT COUNT(*) c FROM staff WHERE active=1").fetchone()["c"],
        "revenue": conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) r FROM bookings WHERE status IN ('checked_in','checked_out','confirmed')"
        ).fetchone()["r"],
    }
    present_today = conn.execute(
        "SELECT COUNT(*) c FROM attendance WHERE work_date=? AND status IN ('present','late')",
        (date.today().isoformat(),)).fetchone()["c"]
    stats["present_today"] = present_today

    recent_bookings = conn.execute(
        "SELECT b.*, r.room_number FROM bookings b LEFT JOIN rooms r ON b.room_id=r.id "
        "ORDER BY b.created_at DESC LIMIT 8").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", stats=stats, recent_bookings=recent_bookings)


@app.route("/admin/bookings")
def admin_bookings():
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    status_filter = request.args.get("status", "")
    query = "SELECT b.*, r.room_number FROM bookings b LEFT JOIN rooms r ON b.room_id=r.id"
    params = ()
    if status_filter:
        query += " WHERE b.status=?"
        params = (status_filter,)
    query += " ORDER BY b.check_in_date DESC"
    bookings = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("admin_bookings.html", bookings=bookings, status_filter=status_filter)


@app.route("/admin/staff")
def admin_staff():
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    staff_list = conn.execute("SELECT * FROM staff WHERE active=1 ORDER BY department").fetchall()
    today = date.today().isoformat()
    attendance_today = {r["staff_id"]: r for r in conn.execute(
        "SELECT * FROM attendance WHERE work_date=?", (today,)).fetchall()}
    conn.close()
    return render_template("admin_staff.html", staff_list=staff_list,
                           attendance_today=attendance_today, today=today)


@app.route("/admin/staff/<int:staff_id>/attendance")
def admin_staff_attendance(staff_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    records = conn.execute(
        "SELECT * FROM attendance WHERE staff_id=? ORDER BY work_date DESC LIMIT 30",
        (staff_id,)).fetchall()
    conn.close()
    return render_template("admin_staff_attendance.html", staff=staff, records=records)


@app.route("/admin/payroll", methods=["GET", "POST"])
def admin_payroll():
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    if request.method == "POST":
        period = request.form.get("period_month", current_month())
        run_payroll_for_month(period, conn=conn)
        flash(f"Autopay run completed for {period}. Salaries disbursed for staff with autopay enabled.", "success")
        conn.close()
        return redirect(url_for("admin_payroll"))

    period = request.args.get("period_month", current_month())
    payroll_rows = conn.execute("""
        SELECT p.*, s.name, s.department, s.role, s.autopay_enabled, s.bank_account
        FROM payroll p JOIN staff s ON p.staff_id = s.id
        WHERE p.period_month = ? ORDER BY s.department""", (period,)).fetchall()
    total_paid = sum(r["net_amount"] for r in payroll_rows if r["status"] == "paid")
    conn.close()
    return render_template("admin_payroll.html", payroll_rows=payroll_rows,
                           period=period, total_paid=total_paid, current_month=current_month())


@app.route("/admin/staff/<int:staff_id>/toggle-autopay", methods=["POST"])
def toggle_autopay(staff_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    conn = get_db()
    staff = conn.execute("SELECT autopay_enabled FROM staff WHERE id=?", (staff_id,)).fetchone()
    new_val = 0 if staff["autopay_enabled"] else 1
    conn.execute("UPDATE staff SET autopay_enabled=? WHERE id=?", (new_val, staff_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("admin_staff"))


if __name__ == "__main__":
    t = threading.Thread(target=autopay_background_worker, daemon=True)
    t.start()
    app.run(debug=True, port=5000)
