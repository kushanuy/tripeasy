"""
booking.py - all the "business logic" of the flight reservation system.

Classes here match the class diagram in the report:
    Flight, Passenger, Booking, BookingSystem
"""
import json
import os
import random
import re
import string
from datetime import date, datetime, timedelta

CITIES = ["Bengaluru", "Delhi", "Mumbai", "Chennai", "Hyderabad", "Kolkata"]
CABINS = {"Economy": 1.0, "Business": 2.5}      # price multiplier
SEATS_PER_FLIGHT = 40
MAX_TRAVELLERS = 6


class BookingError(Exception):
    """Raised when something the user did is not allowed (bad input, no seats...)."""


# ---------------------------------------------------------------- data classes
class Flight:
    def __init__(self, flight_id, airline, origin, destination, dep_time, duration_min, base_price):
        self.flight_id = flight_id
        self.airline = airline
        self.origin = origin
        self.destination = destination
        self.dep_time = dep_time            # "HH:MM"
        self.duration_min = duration_min
        self.base_price = base_price

    @property
    def arr_time(self):
        dep = datetime.strptime(self.dep_time, "%H:%M")
        return (dep + timedelta(minutes=self.duration_min)).strftime("%H:%M")

    @property
    def duration_text(self):
        return f"{self.duration_min // 60}h {self.duration_min % 60:02d}m"

    def price_for(self, cabin):
        return round(self.base_price * CABINS[cabin])


class Passenger:
    def __init__(self, name, age, gender):
        self.name = name
        self.age = age
        self.gender = gender

    def to_dict(self):
        return {"name": self.name, "age": self.age, "gender": self.gender}


class Booking:
    def __init__(self, pnr, flight_id, travel_date, cabin, passengers, email, phone,
                 total_fare, status="CONFIRMED", refund=0):
        self.pnr = pnr
        self.flight_id = flight_id
        self.travel_date = travel_date      # "YYYY-MM-DD"
        self.cabin = cabin
        self.passengers = passengers        # list of Passenger
        self.email = email
        self.phone = phone
        self.total_fare = total_fare
        self.status = status                # CONFIRMED or CANCELLED
        self.refund = refund

    def to_dict(self):
        d = dict(self.__dict__)
        d["passengers"] = [p.to_dict() for p in self.passengers]
        return d

    @staticmethod
    def from_dict(d):
        d = dict(d)
        d["passengers"] = [Passenger(**p) for p in d["passengers"]]
        return Booking(**d)


# ------------------------------------------------------------------ validation
def validate_search(origin, destination, travel_date, travellers, cabin, today=None):
    """Return (travel_date_string, travellers_int) or raise BookingError."""
    today = today or date.today()
    if origin not in CITIES or destination not in CITIES:
        raise BookingError("Please choose both cities from the list.")
    if origin == destination:
        raise BookingError("From and To cities cannot be the same.")
    try:
        d = datetime.strptime(travel_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise BookingError("Please pick a valid travel date.")
    if d < today:
        raise BookingError("Travel date cannot be in the past.")
    try:
        n = int(travellers)
    except (ValueError, TypeError):
        raise BookingError("Travellers must be a number.")
    if not 1 <= n <= MAX_TRAVELLERS:
        raise BookingError(f"You can book 1 to {MAX_TRAVELLERS} travellers at a time.")
    if cabin not in CABINS:
        raise BookingError("Please choose Economy or Business.")
    return travel_date, n


def validate_contact(email, phone):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""):
        raise BookingError("Please enter a valid email address.")
    if not re.fullmatch(r"[6-9]\d{9}", phone or ""):
        raise BookingError("Phone number must be 10 digits (starting with 6-9).")


def validate_passenger(name, age, gender):
    name = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,39}", name):
        raise BookingError(f"Invalid passenger name: '{name}'. Use letters only.")
    try:
        age = int(age)
    except (ValueError, TypeError):
        raise BookingError(f"Age for {name} must be a number.")
    if not 0 <= age <= 120:
        raise BookingError(f"Age for {name} must be between 0 and 120.")
    if gender not in ("Male", "Female", "Other"):
        raise BookingError(f"Please choose a gender for {name}.")
    return Passenger(name.title(), age, gender)


# --------------------------------------------------------------- main controller
class BookingSystem:
    """Holds flights and bookings. Saves bookings to a JSON file (if a path is given)."""

    def __init__(self, storage_path=None):
        self.storage_path = storage_path
        self.flights = self._make_flights()
        self.bookings = {}
        self._load()

    # ---- flights --------------------------------------------------------
    @staticmethod
    def _make_flights():
        airlines = [("IndiGo", "6E"), ("Air India", "AI"), ("Vistara", "UK"), ("SpiceJet", "SG")]
        times = ["06:15", "09:40", "13:10", "17:55", "21:30"]
        flights = {}
        n = 100
        for o in CITIES:
            for d in CITIES:
                if o == d:
                    continue
                dist = abs(CITIES.index(o) - CITIES.index(d))
                for i, t in enumerate(times):
                    name, code = airlines[(n + i) % len(airlines)]
                    n += 1
                    fid = f"{code}{n}"
                    flights[fid] = Flight(fid, name, o, d, t,
                                          duration_min=75 + dist * 20,
                                          base_price=3200 + dist * 450 + i * 300)
        return flights

    def search(self, origin, destination, travel_date, travellers, cabin, today=None, now=None):
        """Return a list of (flight, seats_left, price_per_person) that can fit the travellers."""
        travel_date, n = validate_search(origin, destination, travel_date, travellers, cabin, today)
        now = self._now(today, now)
        results = []
        for f in self.flights.values():
            if f.origin == origin and f.destination == destination:
                if self.departure(f.flight_id, travel_date) <= now:
                    continue                # already left today, so do not show it
                left = self.seats_left(f.flight_id, travel_date)
                if left >= n:
                    results.append((f, left, f.price_for(cabin)))
        results.sort(key=lambda r: r[2])    # cheapest first
        return results

    def seats_left(self, flight_id, travel_date):
        used = sum(len(b.passengers) for b in self.bookings.values()
                   if b.flight_id == flight_id and b.travel_date == travel_date
                   and b.status == "CONFIRMED")
        return SEATS_PER_FLIGHT - used

    # ---- bookings -------------------------------------------------------
    def create_booking(self, flight_id, travel_date, cabin, passenger_rows, email, phone,
                       today=None, now=None):
        """passenger_rows = list of (name, age, gender). Returns the new Booking."""
        flight = self.flights.get(flight_id)
        if flight is None:
            raise BookingError("That flight does not exist.")
        validate_search(flight.origin, flight.destination, travel_date,
                        len(passenger_rows) or 1, cabin, today)
        if self.departure(flight_id, travel_date) <= self._now(today, now):
            raise BookingError("This flight has already departed. Please choose a later flight.")
        if not passenger_rows:
            raise BookingError("Add at least one passenger.")
        validate_contact(email, phone)
        passengers = [validate_passenger(*row) for row in passenger_rows]
        if self.seats_left(flight_id, travel_date) < len(passengers):
            raise BookingError("Sorry, not enough seats are left on this flight.")
        pnr = self._new_pnr()
        booking = Booking(pnr, flight_id, travel_date, cabin, passengers,
                          email.strip().lower(), phone,
                          total_fare=flight.price_for(cabin) * len(passengers))
        self.bookings[pnr] = booking
        self._save()
        return booking

    def find_booking(self, pnr, email):
        b = self.bookings.get((pnr or "").strip().upper())
        if b is None or b.email != (email or "").strip().lower():
            raise BookingError("No booking found for that PNR and email.")
        return b

    def cancel_booking(self, pnr, email, now=None):
        """Refund: 90% if more than 24 hours before departure, else 50%."""
        b = self.find_booking(pnr, email)
        if b.status == "CANCELLED":
            raise BookingError("This booking is already cancelled.")
        now = now or datetime.now()
        dep = self.departure(b.flight_id, b.travel_date)
        if dep <= now:
            raise BookingError("This flight has already departed, so it cannot be cancelled.")
        rate = 0.9 if dep - now > timedelta(hours=24) else 0.5
        b.refund = round(b.total_fare * rate)
        b.status = "CANCELLED"
        self._save()
        return b

    # ---- helpers --------------------------------------------------------
    def departure(self, flight_id, travel_date):
        """Date and time the flight leaves on the given travel date."""
        return datetime.strptime(f"{travel_date} {self.flights[flight_id].dep_time}", "%Y-%m-%d %H:%M")

    @staticmethod
    def _now(today=None, now=None):
        """Current time. If only a test 'today' is given, use the start of that day."""
        if now:
            return now
        return datetime.combine(today, datetime.min.time()) if today else datetime.now()

    def _new_pnr(self):
        while True:
            pnr = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if pnr not in self.bookings:
                return pnr

    def _save(self):
        if self.storage_path:
            with open(self.storage_path, "w") as f:
                json.dump([b.to_dict() for b in self.bookings.values()], f, indent=2)

    def _load(self):
        if self.storage_path and os.path.exists(self.storage_path):
            with open(self.storage_path) as f:
                for d in json.load(f):
                    b = Booking.from_dict(d)
                    self.bookings[b.pnr] = b
