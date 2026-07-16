# HappyStayz — Smart Hotel Management System

A working hotel management web app with:
- 🛎️ **Guest self check-in** (enter a booking code → get a digital room key instantly)
- 📅 **Online room booking**
- ⏱️ **Smart staff attendance** (staff clock in/out themselves; late/present/absent tracked automatically)
- 💰 **Automatic payroll (autopay)** — salary is calculated from attendance and auto-disbursed to staff every month, with a manual "Run Autopay Now" button for demos
- 📊 **Admin dashboard** — bookings, occupancy, staff attendance, payroll history

Built with **Python Flask + SQLite** (no external database server, no complicated setup).
Seeded with a realistic dataset structured like Kaggle's popular **"Hotel Booking Demand"** dataset (same columns: lead time, ADR, market segment, country, cancellation status, etc.) — see the "About the dataset" section below.

---

## 1. Requirements

- Python 3.9 or newer (Python 3.12 recommended)
- pip (comes with Python)

Check your Python version:
```bash
python3 --version
```
If you don't have Python installed, download it from https://www.python.org/downloads/ (on Windows, tick "Add Python to PATH" during install).

---

## 2. Installation

1. Unzip/copy the `HappyStayz` folder to anywhere on your computer, e.g. `Desktop/HappyStayz`.
2. Open a terminal (Command Prompt / PowerShell / macOS Terminal / Linux shell) **inside that folder**:
   ```bash
   cd path/to/HappyStayz
   ```
3. (Recommended) Create a virtual environment so this doesn't affect other Python projects:
   ```bash
   python3 -m venv venv
   ```
   Activate it:
   - **Windows**: `venv\Scripts\activate`
   - **macOS/Linux**: `source venv/bin/activate`
4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

That's it — only Flask is required. No database server, no Node.js, no build step.

---

## 3. Running the app

```bash
python3 app.py
```

You should see:
```
Database initialized and seeded.
 * Running on http://127.0.0.1:5000
```

Open your browser and go to: **http://127.0.0.1:5000**

The first time you run it, a SQLite database (`instance/happystayz.db`) is created automatically and seeded with:
- 40 rooms across 5 floors (Standard, Deluxe, Executive Suite, Family Room, Presidential Suite)
- 10 staff members across Front Desk, Housekeeping, Kitchen, Maintenance, Security, and Management
- 60 sample bookings (drawn from the Kaggle-style dataset in `data/hotel_bookings.csv`)
- 30 days of attendance history for every staff member, so payroll has real numbers to work with from day one

To stop the server, press `CTRL+C` in the terminal.

**To reset the data** (wipe and reseed from scratch), delete `instance/happystayz.db` and restart the app.

---

## 4. How to use it

### As a guest
- Go to **Book a Room** to make a reservation → you'll get a booking code like `HSZ100000`.
- Go to **Self Check-In**, enter that code, and you'll instantly get a room number and a digital key code — no front desk needed.

### As staff
- Go to **Staff Login**. Demo accounts (password is `staff123` for everyone, on a fresh install):
  | Username | Name | Department | Role |
  |---|---|---|---|
  | `ananya1` | Ananya Gupta | Front Desk | Front Desk Executive |
  | `diya2` | Diya Chatterjee | Front Desk | Front Desk Executive |
  | `aarav3` | Aarav Verma | Housekeeping | Housekeeping Staff |
  | `priya4` | Priya Kapoor | Housekeeping | Housekeeping Staff |
  | `vivaan5` | Vivaan Mishra | Housekeeping | Housekeeping Supervisor |
  | `riya6` | Riya Sharma | Kitchen | Chef |
  | `karan7` | Karan Kapoor | Kitchen | Kitchen Assistant |
  | `ishaan8` | Ishaan Sharma | Maintenance | Maintenance Technician |
  | `vivaan9` | Vivaan Nair | Security | Security Guard |
  | `diya10` | Diya Verma | Management | Duty Manager |

  (The random seed is fixed in `database.py`, so these will match exactly on any fresh install.)
- On the Staff Dashboard, click **Check In** when you start your shift and **Check Out** when you finish. Hours worked and late/present status are calculated automatically.

### As admin
- Go to **Admin Login** → username `admin`, password `admin123`.
- **Admin Dashboard**: occupancy, revenue, staff present today, recent bookings.
- **Staff & Attendance**: see who's checked in today, view 30-day history per staff member, and toggle **Autopay ON/OFF** per staff member.
- **Payroll / Autopay**: pick a month and click **"Run Autopay Now"**. This computes each staff member's salary from their logged attendance hours (hours × hourly rate, minus a 2% notional deduction) and immediately marks it **paid** with a transaction reference — for anyone with autopay enabled. Staff with autopay disabled show as "pending" until an admin approves manually (a hook you can extend later).
- Autopay also **runs automatically in the background** on the 1st of every month for the previous month's attendance (a background thread checks this hourly while the server is running) — this is the "autopay saved" feature you asked for.

---

## 5. Project structure

```
HappyStayz/
├── app.py                  # Flask app: all routes (guest, staff, admin)
├── database.py              # SQLite schema + seeding logic
├── requirements.txt
├── data/
│   ├── generate_dataset.py  # generates the Kaggle-style CSV
│   └── hotel_bookings.csv   # synthetic dataset, same schema as Kaggle's
├── instance/
│   └── happystayz.db        # created automatically on first run
├── templates/                # all HTML pages (Jinja2 + Bootstrap 5)
└── static/
    └── css/style.css         # HappyStayz branding
```

---

## 6. About the dataset

`data/hotel_bookings.csv` is generated to match the **exact column structure** of the well-known Kaggle dataset **"Hotel Booking Demand"** (Antonio, Almeida & Nunes, 2019) — `lead_time`, `arrival_date_*`, `adr`, `market_segment`, `country`, `reservation_status`, etc. I generated it synthetically instead of downloading it live, since this environment has no internet access — but because the column names and structure match exactly, you can swap in the real dataset with zero code changes:

1. Go to https://www.kaggle.com/datasets/jessemostipak/hotel-booking-demand and download `hotel_bookings.csv`.
2. Replace `data/hotel_bookings.csv` with it (keep the same filename).
3. Delete `instance/happystayz.db` and restart the app — it will reseed using the real Kaggle data.

(Note: the real dataset doesn't include Indian Rupee pricing or Indian guest names — you may want to adjust `database.py`'s seeding logic for currency/locale if you swap it in.)

---

## 7. Ideas to extend this further

- Add real payment gateway integration (Razorpay/Stripe) instead of the simulated transaction reference
- Add face-recognition or QR-code based attendance instead of button-click check-in
- SMS/email the digital key code to guests automatically
- Export payroll as a payslip PDF for each staff member
- Role-based staff permissions (e.g., only managers can view payroll)

---

## 8. Troubleshooting

- **"Address already in use"** → another program is using port 5000. Change the last line of `app.py` to `app.run(debug=True, port=5050)` and visit `http://127.0.0.1:5050` instead.
- **"No module named flask"** → make sure you activated the virtual environment (step 3) and ran `pip install -r requirements.txt`.
- **Data looks wrong / want a clean slate** → delete `instance/happystayz.db` and restart the app.
