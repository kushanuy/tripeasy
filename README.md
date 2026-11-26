# TripEasy – Flight Reservation Website (CSC203B)

## Run it
```
pip install -r requirements.txt
python app.py
```
Open  in your browser.

## Run the tests
```
python -m pytest -v
```

## Files
| File | What it does |
|------|--------------|
| `booking.py` | All the logic: Flight, Passenger, Booking, BookingSystem classes + validation |
| `app.py` | The website pages (Flask routes) |
| `templates/` | HTML pages (home, results, book, confirmation, manage) |
| `static/style.css` | Styling |
| `auth.py` | Accounts + login. Hard-coded account kushanuy@gmail.com (its saved details auto-fill bookings); everyone else creates an account first |
| `test_tripeasy.py` | 40 test cases (TC01–TC40) |
| `bookings.json`, `accounts.json` | Created automatically; store bookings and new accounts so they survive restart |

## Login
- Hard-coded account: `kushanuy@gmail.com` / `abcd12345`
- Any other email: click **Create an account** when asked to log in during booking.
