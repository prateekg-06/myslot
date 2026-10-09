import os
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import create_app


class AppointmentApiTests(unittest.TestCase):
    def setUp(self):
        self.database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.database_file.close()
        self.current_time = datetime(2030, 5, 8, 14, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_file.name,
                "NOW_PROVIDER": lambda: self.current_time,
            }
        )
        self.client = self.app.test_client()
        self.future_date = (self.current_time.date() + timedelta(days=1)).isoformat()
        self.payload = {
            "customer_name": "Alex Morgan",
            "email": "alex@example.com",
            "service_type": "Consultation",
            "appointment_date": self.future_date,
            "time_slot": "09:00",
        }

    def tearDown(self):
        os.unlink(self.database_file.name)

    def test_creates_an_appointment(self):
        response = self.client.post("/api/appointments", json=self.payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["appointment"]["customer_name"], "Alex Morgan")
        self.assertEqual(response.json["appointment"]["time_label"], "9:00 AM")

    def test_rejects_duplicate_slot_booking(self):
        self.client.post("/api/appointments", json=self.payload)
        response = self.client.post("/api/appointments", json=self.payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "Selected time slot is already booked.")

    def test_slots_mark_booked_time_as_unavailable(self):
        self.client.post("/api/appointments", json=self.payload)
        response = self.client.get(f"/api/slots?date={self.future_date}")
        slots = {slot["time"]: slot for slot in response.json["slots"]}

        self.assertFalse(slots["09:00"]["available"])
        self.assertTrue(slots["09:30"]["available"])

    def test_rejects_a_past_date(self):
        self.payload["appointment_date"] = (self.current_time.date() - timedelta(days=1)).isoformat()
        response = self.client.post("/api/appointments", json=self.payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("appointment_date", response.json["fields"])

    def test_marks_elapsed_time_slots_as_unavailable_today(self):
        response = self.client.get(f"/api/slots?date={self.current_time.date().isoformat()}")
        slots = {slot["time"]: slot for slot in response.json["slots"]}

        self.assertFalse(slots["14:00"]["available"])
        self.assertTrue(slots["14:30"]["available"])

    def test_rejects_a_time_slot_that_has_already_passed_today(self):
        self.payload["appointment_date"] = self.current_time.date().isoformat()
        self.payload["time_slot"] = "14:00"
        response = self.client.post("/api/appointments", json=self.payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["fields"]["time_slot"], "Selected time slot has already passed.")


if __name__ == "__main__":
    unittest.main()
