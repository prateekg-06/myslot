from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "appointments.db"
TIME_SLOTS = [
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
    "16:00",
    "16:30",
]
SERVICES = [
    {"name": "Consultation", "duration": "30 min", "description": "A focused session to plan your next step."},
    {"name": "Strategy Session", "duration": "30 min", "description": "A deeper working session for complex goals."},
    {"name": "Follow-up", "duration": "30 min", "description": "Review progress and keep your work moving."},
]
SERVICE_NAMES = {service["name"] for service in SERVICES}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BUSINESS_TIMEZONE = ZoneInfo("Asia/Kolkata")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(DATABASE_PATH),
        NOW_PROVIDER=lambda: datetime.now(BUSINESS_TIMEZONE),
    )

    if test_config:
        app.config.update(test_config)

    with app.app_context():
        initialize_database(app.config["DATABASE"])

    @app.get("/")
    def index():
        return render_template("index.html", services=SERVICES)

    @app.get("/api/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.get("/api/slots")
    def get_slots():
        now = current_business_time(app)
        appointment_date, error = parse_appointment_date(request.args.get("date", ""), now.date())
        if error:
            return jsonify({"error": error}), 400

        with get_connection(app.config["DATABASE"]) as connection:
            booked_slots = {
                row["time_slot"]
                for row in connection.execute(
                    "SELECT time_slot FROM appointments WHERE appointment_date = ?", (appointment_date,)
                )
            }

        return jsonify(
            {
                "date": appointment_date,
                "slots": [
                    {
                        "time": slot,
                        "label": format_time(slot),
                        "available": slot not in booked_slots and not slot_has_passed(appointment_date, slot, now),
                    }
                    for slot in TIME_SLOTS
                ],
            }
        )

    @app.get("/api/appointments")
    def list_appointments():
        requested_date = request.args.get("date")
        query = "SELECT * FROM appointments"
        params: tuple[str, ...] = ()

        if requested_date:
            appointment_date, error = parse_appointment_date(requested_date, current_business_time(app).date())
            if error:
                return jsonify({"error": error}), 400
            query += " WHERE appointment_date = ?"
            params = (appointment_date,)

        query += " ORDER BY appointment_date ASC, time_slot ASC"
        with get_connection(app.config["DATABASE"]) as connection:
            appointments = [serialize_appointment(row) for row in connection.execute(query, params)]

        return jsonify({"appointments": appointments})

    @app.post("/api/appointments")
    def create_appointment():
        data = request.get_json(silent=True) or {}
        cleaned_data, errors = validate_booking(data, current_business_time(app))
        if errors:
            return jsonify({"error": "Please correct the highlighted fields.", "fields": errors}), 400

        try:
            with get_connection(app.config["DATABASE"]) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO appointments (customer_name, email, service_type, appointment_date, time_slot)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        cleaned_data["customer_name"],
                        cleaned_data["email"],
                        cleaned_data["service_type"],
                        cleaned_data["appointment_date"],
                        cleaned_data["time_slot"],
                    ),
                )
                appointment_id = cursor.lastrowid
                appointment = connection.execute(
                    "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
                ).fetchone()
        except sqlite3.IntegrityError:
            return jsonify({"error": "Selected time slot is already booked."}), 409

        return (
            jsonify(
                {
                    "message": "Your appointment has been successfully scheduled.",
                    "appointment": serialize_appointment(appointment),
                }
            ),
            201,
        )

    @app.delete("/api/appointments/<int:appointment_id>")
    def delete_appointment(appointment_id: int):
        with get_connection(app.config["DATABASE"]) as connection:
            cursor = connection.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))

        if cursor.rowcount == 0:
            return jsonify({"error": "Appointment not found."}), 404
        return jsonify({"message": "Appointment cancelled."})

    return app


@contextmanager
def get_connection(database: str):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(database: str) -> None:
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                email TEXT NOT NULL,
                service_type TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(appointment_date, time_slot)
            )
            """
        )
        connection.commit()


def current_business_time(app: Flask) -> datetime:
    now = app.config["NOW_PROVIDER"]()
    if now.tzinfo is None:
        return now.replace(tzinfo=BUSINESS_TIMEZONE)
    return now.astimezone(BUSINESS_TIMEZONE)


def parse_appointment_date(value: str, today_value=None) -> tuple[str | None, str | None]:
    try:
        selected_date = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None, "Enter a valid appointment date."

    if today_value is None:
        today_value = datetime.now(BUSINESS_TIMEZONE).date()
    if selected_date < today_value:
        return None, "Appointments cannot be scheduled in the past."
    return selected_date.isoformat(), None


def validate_booking(data: dict, now: datetime | None = None) -> tuple[dict, dict]:
    cleaned = {
        "customer_name": str(data.get("customer_name", "")).strip(),
        "email": str(data.get("email", "")).strip().lower(),
        "service_type": str(data.get("service_type", "")).strip(),
        "appointment_date": str(data.get("appointment_date", "")).strip(),
        "time_slot": str(data.get("time_slot", "")).strip(),
    }
    errors = {}

    if len(cleaned["customer_name"]) < 2 or len(cleaned["customer_name"]) > 80:
        errors["customer_name"] = "Enter a name between 2 and 80 characters."
    if not EMAIL_PATTERN.fullmatch(cleaned["email"]):
        errors["email"] = "Enter a valid email address."
    if cleaned["service_type"] not in SERVICE_NAMES:
        errors["service_type"] = "Choose a service from the list."
    now = now or datetime.now(BUSINESS_TIMEZONE)
    parsed_date, date_error = parse_appointment_date(cleaned["appointment_date"], now.date())
    if date_error:
        errors["appointment_date"] = date_error
    else:
        cleaned["appointment_date"] = parsed_date
    if cleaned["time_slot"] not in TIME_SLOTS:
        errors["time_slot"] = "Choose an available time slot."
    elif parsed_date and slot_has_passed(parsed_date, cleaned["time_slot"], now):
        errors["time_slot"] = "Selected time slot has already passed."

    return cleaned, errors


def slot_has_passed(appointment_date: str, time_slot: str, now: datetime) -> bool:
    slot_start = datetime.strptime(f"{appointment_date} {time_slot}", "%Y-%m-%d %H:%M").replace(
        tzinfo=BUSINESS_TIMEZONE
    )
    return slot_start <= now


def format_time(value: str) -> str:
    parsed_time = datetime.strptime(value, "%H:%M")
    hour = parsed_time.hour % 12 or 12
    return f"{hour}:{parsed_time:%M} {parsed_time:%p}"


def serialize_appointment(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "email": row["email"],
        "service_type": row["service_type"],
        "appointment_date": row["appointment_date"],
        "time_slot": row["time_slot"],
        "time_label": format_time(row["time_slot"]),
        "created_at": row["created_at"],
    }


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
