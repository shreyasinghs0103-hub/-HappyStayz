"""
Generates data/hotel_bookings.csv in the same schema as the well-known
Kaggle 'Hotel Booking Demand' dataset (Antonio, Almeida and Nunes, 2019).
Column structure matches the real dataset so you can later swap in the
actual Kaggle CSV (kaggle datasets download -d jessemostipak/hotel-booking-demand)
without changing any app code.
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
COUNTRIES = ["IND", "USA", "GBR", "DEU", "FRA", "ARE", "SGP", "AUS", "CAN", "NPL"]
MEAL = ["BB", "HB", "FB", "SC"]
MARKET_SEGMENT = ["Online TA", "Offline TA/TO", "Direct", "Corporate", "Groups"]
DIST_CHANNEL = ["TA/TO", "Direct", "Corporate"]
ROOM_TYPES = ["A", "B", "C", "D", "E"]
DEPOSIT = ["No Deposit", "Non Refund", "Refundable"]
CUSTOMER_TYPE = ["Transient", "Transient-Party", "Contract", "Group"]

rows = []
start = date(2025, 1, 1)

for i in range(600):
    arrival = start + timedelta(days=random.randint(0, 545))
    lead_time = random.randint(0, 200)
    is_canceled = 1 if random.random() < 0.18 else 0
    weekend_nights = random.randint(0, 3)
    week_nights = random.randint(0, 6)
    adults = random.choice([1, 1, 2, 2, 2, 3])
    children = random.choice([0, 0, 0, 0, 1, 2])
    babies = random.choice([0, 0, 0, 1])
    room_type = random.choice(ROOM_TYPES)
    adr = round(random.uniform(1800, 9500), 2)  # price per night in INR
    reservation_status = "Canceled" if is_canceled else random.choice(
        ["Check-Out", "Check-Out", "Check-Out", "No-Show"])
    status_date = arrival + timedelta(days=weekend_nights + week_nights)

    rows.append({
        "hotel": "HappyStayz Resort",
        "is_canceled": is_canceled,
        "lead_time": lead_time,
        "arrival_date_year": arrival.year,
        "arrival_date_month": MONTHS[arrival.month - 1],
        "arrival_date_day_of_month": arrival.day,
        "stays_in_weekend_nights": weekend_nights,
        "stays_in_week_nights": week_nights,
        "adults": adults,
        "children": children,
        "babies": babies,
        "meal": random.choice(MEAL),
        "country": random.choice(COUNTRIES),
        "market_segment": random.choice(MARKET_SEGMENT),
        "distribution_channel": random.choice(DIST_CHANNEL),
        "is_repeated_guest": 1 if random.random() < 0.12 else 0,
        "previous_cancellations": random.choice([0, 0, 0, 1]),
        "previous_bookings_not_canceled": random.choice([0, 0, 1, 2]),
        "reserved_room_type": room_type,
        "assigned_room_type": room_type if random.random() > 0.1 else random.choice(ROOM_TYPES),
        "booking_changes": random.choice([0, 0, 0, 1, 2]),
        "deposit_type": random.choice(DEPOSIT),
        "days_in_waiting_list": 0,
        "customer_type": random.choice(CUSTOMER_TYPE),
        "adr": adr,
        "required_car_parking_spaces": random.choice([0, 0, 0, 1]),
        "total_of_special_requests": random.choice([0, 1, 1, 2, 3]),
        "reservation_status": reservation_status,
        "reservation_status_date": status_date.isoformat(),
        "guest_name": None,   # filled in by seed_db.py per-booking
        "guest_email": None,
    })

fieldnames = list(rows[0].keys())
with open("/home/claude/HappyStayz/data/hotel_bookings.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows -> data/hotel_bookings.csv")
