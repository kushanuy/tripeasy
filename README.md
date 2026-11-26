# TripEasy – Flight Reservation Website (CSC203B)

## Run it
```
pip install -r requirements.txt
python app.py
```
Open https://tripeasy-vn8x.onrender.com in your browser.

## Deploy to Render
1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render reads `render.yaml`, installs `requirements.txt`, and starts the app with Gunicorn. The secret key is generated automatically.

The included free web service uses local JSON files for bookings and accounts. Render's free filesystem is ephemeral, so those records can be lost when the service restarts or redeploys. Use a persistent disk or external database before relying on this for real bookings.

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
