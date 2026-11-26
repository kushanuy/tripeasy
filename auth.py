"""
auth.py - accounts and login for TripEasy.

 * One account is HARD-CODED: kushanuy@gmail.com (password abcd12345, stored as a hash).
   Its saved details are used to auto-fill the booking form.
 * Any other email has no account until the user creates one with "Create account".
"""
import json
import os

from werkzeug.security import check_password_hash, generate_password_hash

from booking import BookingError, validate_contact, validate_passenger

HARDCODED_EMAIL = "kushanuy@gmail.com"
HARDCODED_PASSWORD_HASH = ("pbkdf2:sha256:1000000$ItvCzT618i6uRqMQ$"
                           "3d06d0f34dd3bd1fc713562dacaf45e262651bf29bb15d514c2b29ce1ae25470")
# Saved details of the hard-coded account (used to auto-fill the booking form)
HARDCODED_PROFILE = {"name": "Kushanu Y", "age": 20, "gender": "Male", "phone": "9876543210"}

MIN_PASSWORD_LENGTH = 8


class NoAccountError(BookingError):
    """Raised when someone tries to log in with an email that has no account yet."""


class AccountStore:
    """Keeps all accounts. New accounts are saved to a JSON file (if a path is given)."""

    def __init__(self, path=None):
        self.path = path
        self.accounts = {
            HARDCODED_EMAIL: dict(HARDCODED_PROFILE, email=HARDCODED_EMAIL, password_hash=HARDCODED_PASSWORD_HASH)
        }
        if path and os.path.exists(path):
            with open(path) as f:
                for acc in json.load(f):
                    self.accounts.setdefault(acc["email"], acc)

    @staticmethod
    def _clean(email):
        return (email or "").strip().lower()

    def get(self, email):
        """Return the saved profile (without the password) or None."""
        acc = self.accounts.get(self._clean(email))
        if acc is None:
            return None
        return {k: v for k, v in acc.items() if k != "password_hash"}

    def authenticate(self, email, password):
        """Return the account's email if the login is correct, else raise an error."""
        email = self._clean(email)
        if not email or not password:
            raise BookingError("Please enter your email and password.")
        acc = self.accounts.get(email)
        if acc is None:
            raise NoAccountError("No account found for this email. Please create an account.")
        if not check_password_hash(acc["password_hash"], password):
            raise BookingError("Incorrect password.")
        return email

    def signup(self, name, age, gender, email, phone, password):
        """Create a new account. Raises BookingError if anything is invalid."""
        passenger = validate_passenger(name, age, gender)       # re-use the booking checks
        email = self._clean(email)
        validate_contact(email, phone)
        if email in self.accounts:
            raise BookingError("An account with this email already exists. Please log in.")
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise BookingError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        self.accounts[email] = {"name": passenger.name, "age": passenger.age,
                                "gender": passenger.gender, "email": email, "phone": phone,
                                "password_hash": generate_password_hash(password)}
        self._save()
        return email

    def _save(self):
        if self.path:
            extra = [a for e, a in self.accounts.items() if e != HARDCODED_EMAIL]   # hard-coded one lives in code
            with open(self.path, "w") as f:
                json.dump(extra, f, indent=2)
