# my-slot | Appointment Scheduling Platform

my-slot is a full-stack appointment scheduling application that demonstrates how a customer-facing booking experience connects to reliable backend scheduling rules. It provides live slot availability, prevents double bookings, stores appointment history, and gives a service provider a daily schedule view.

## What This Project Demonstrates

| Core skill | Where it is demonstrated |
| --- | --- |
| Full-stack web development | Flask REST API connected to a responsive HTML and JavaScript interface |
| Database design | SQLite appointment records with timestamps and a unique scheduling constraint |
| Business-rule implementation | Backend validation for services, dates, time slots, email addresses, and required values |
| Conflict prevention | Duplicate bookings return HTTP `409`; SQLite enforces one appointment per date and time slot |
| UI/UX engineering | Mobile-first Tailwind interface with accessible forms, immediate availability feedback, and booking states |
| API design | Focused endpoints for appointment creation, availability, daily schedules, cancellation, and health checks |
| Test-driven verification | Automated coverage for successful bookings, unavailable slots, conflicts, and past-date validation |

## Highlights

- Customers can select a service, date, and an available 30-minute slot.
- Availability is loaded from the database for the chosen day.
- For the current day, slots whose start time has already passed are disabled using the `Asia/Kolkata` business timezone.
- The backend validates all booking data before a record is created.
- A database-level `UNIQUE(appointment_date, time_slot)` constraint prevents race-condition double bookings.
- Successful bookings appear in the provider schedule immediately.
- Providers can review daily appointments and cancel a booking when needed.
- The editorial `my-slot` interface adapts cleanly from desktop to mobile.

## Booking Flow and Output

1. The customer selects a service, date, and an available time slot.
2. The selected slot receives an active visual state before submission.
3. After **Confirm appointment** is selected, the Flask API validates the request and checks availability again.
4. On success, the interface displays a confirmation message with the booked date and time.
5. The daily tracker updates its scheduled count, open-slot count, next appointment, and appointment list. The newly booked slot becomes unavailable.

If the slot is already booked, its start time has passed, or the submitted details are invalid, the API rejects the request with a clear message instead of creating an appointment.

## Tech Stack

- **Frontend:** HTML5, Tailwind CSS, vanilla JavaScript, Lucide icons
- **Backend:** Python 3, Flask
- **Database:** SQLite
- **Testing:** Python `unittest`

## Architecture

```text
Browser UI
    |
    |  Fetch API requests
    v
Flask application
    |
    |  Validation + slot conflict checks
    v
SQLite database
    |
    +-- appointments(id, customer_name, email, service_type,
                      appointment_date, time_slot, created_at)
```

The database stores appointments locally at `data/appointments.db`. It is created automatically on the first run and excluded from Git.

## Project Structure

```text
project2/
├── app.py                 # Flask routes, validation, and SQLite access
├── requirements.txt       # Python dependency list
├── templates/
│   └── index.html         # Tailwind-powered scheduling interface
├── static/
│   └── app.js             # Booking, slot, and schedule interactions
└── tests/
    └── test_app.py        # API and scheduling-rule tests
```

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in a browser.

## Run Tests

```bash
python -m unittest discover -s tests -v
```

The test suite verifies booking creation, past-date rejection, elapsed-slot handling, slot availability, and duplicate-slot conflict handling.

## API Reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Confirm that the application is running |
| `GET` | `/api/slots?date=YYYY-MM-DD` | Return the available and booked slots for a date |
| `GET` | `/api/appointments?date=YYYY-MM-DD` | Return a day's appointment schedule |
| `POST` | `/api/appointments` | Validate and create an appointment |
| `DELETE` | `/api/appointments/:id` | Cancel an appointment |

Example booking request:

```json
{
  "customer_name": "Alex Morgan",
  "email": "alex@example.com",
  "service_type": "Consultation",
  "appointment_date": "2026-10-10",
  "time_slot": "09:00"
}
```

When a slot has already been booked, the API returns HTTP `409`:

```json
{
  "error": "Selected time slot is already booked."
}
```

## GitHub Publishing Checklist

```bash
git init
git add .
git commit -m "Build my-slot appointment scheduling platform"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```
