"""
app.py - the website (Flask). Run with:  python app.py   then open http://127.0.0.1:5000
"""
from datetime import date
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for

from auth import AccountStore, NoAccountError
from booking import BookingError, BookingSystem, CABINS, CITIES, MAX_TRAVELLERS


def create_app(storage_path=None, accounts_path=None):
    app = Flask(__name__)
    app.secret_key = "school-project-secret"      # needed for flash messages
    system = BookingSystem(storage_path)
    app.config["SYSTEM"] = system
    accounts = AccountStore(accounts_path)
    app.config["ACCOUNTS"] = accounts

    def login_required(view):
        """Send people who are not logged in to the login page."""
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            return view(*args, **kwargs)
        return wrapper

    @app.context_processor
    def common():
        return {"user": session.get("user"), "cities": CITIES, "cabins": list(CABINS), "today": date.today().isoformat(),
                "max_travellers": MAX_TRAVELLERS}

    @app.route("/")
    def home():
        return render_template("index.html")

    def safe_next():
        """Where to go after login. Only our own pages are allowed."""
        nxt = request.values.get("next", "")
        return nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("home")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        nxt = safe_next()
        no_account = False
        if request.method == "POST":
            try:
                session["user"] = accounts.authenticate(request.form.get("email"), request.form.get("password"))
                flash("Logged in successfully.", "success")
                return redirect(nxt)
            except NoAccountError as e:
                flash(str(e), "error")
                no_account = True
            except BookingError as e:
                flash(str(e), "error")
        return render_template("login.html", next=nxt, no_account=no_account)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        nxt = safe_next()
        if request.method == "POST":
            f = request.form
            try:
                session["user"] = accounts.signup(f.get("name"), f.get("age"), f.get("gender"),
                                                  f.get("email"), f.get("phone"), f.get("password"))
                flash("Account created! You are now logged in.", "success")
                return redirect(nxt)
            except BookingError as e:
                flash(str(e), "error")
        return render_template("signup.html", next=nxt)

    @app.route("/logout")
    def logout():
        session.pop("user", None)
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    @app.route("/search")
    def search():
        a = request.args
        try:
            results = system.search(a.get("origin"), a.get("destination"), a.get("date"),
                                    a.get("travellers"), a.get("cabin"))
        except BookingError as e:
            flash(str(e), "error")
            return redirect(url_for("home"))
        return render_template("results.html", results=results, q=a)

    @app.route("/book/<flight_id>")
    @login_required
    def book_form(flight_id):
        flight = system.flights.get(flight_id)
        if flight is None:
            flash("That flight does not exist.", "error")
            return redirect(url_for("home"))
        a = request.args
        try:
            n = int(a.get("travellers", 1))
        except ValueError:
            n = 1
        cabin = a.get("cabin", "Economy")
        if cabin not in CABINS:
            cabin = "Economy"
        return render_template("book.html", flight=flight, date=a.get("date"), n=max(1, min(n, MAX_TRAVELLERS)),
                               cabin=cabin, price=flight.price_for(cabin),
                               profile=accounts.get(session["user"]))

    @app.route("/book/<flight_id>", methods=["POST"])
    @login_required
    def book_submit(flight_id):
        f = request.form
        try:
            n = int(f.get("travellers", 1))
        except ValueError:
            n = 0
        if not 1 <= n <= MAX_TRAVELLERS:            # someone edited the hidden field
            flash(f"You can book 1 to {MAX_TRAVELLERS} travellers at a time.", "error")
            return redirect(url_for("home"))
        rows = [(f.get(f"name{i}"), f.get(f"age{i}"), f.get(f"gender{i}")) for i in range(n)]
        try:
            b = system.create_booking(flight_id, f.get("date"), f.get("cabin"), rows,
                                      session["user"], f.get("phone"))
        except BookingError as e:
            flash(str(e), "error")
            return redirect(url_for("book_form", flight_id=flight_id, date=f.get("date"),
                                    travellers=n, cabin=f.get("cabin")))
        return redirect(url_for("confirmation", pnr=b.pnr))

    @app.route("/confirmation/<pnr>")
    @login_required
    def confirmation(pnr):
        b = system.bookings.get(pnr)
        if b is None or b.email != session["user"]:     # only the owner may see it
            flash("Booking not found.", "error")
            return redirect(url_for("home"))
        return render_template("confirmation.html", b=b, flight=system.flights[b.flight_id])

    @app.route("/manage", methods=["GET", "POST"])
    @login_required
    def manage():
        booking = None
        if request.method == "POST":
            try:
                booking = system.find_booking(request.form.get("pnr"), request.form.get("email"))
            except BookingError as e:
                flash(str(e), "error")
        return render_template("manage.html", b=booking,
                               flight=system.flights[booking.flight_id] if booking else None)

    @app.route("/cancel", methods=["POST"])
    @login_required
    def cancel():
        try:
            b = system.cancel_booking(request.form.get("pnr"), request.form.get("email"))
            flash(f"Booking {b.pnr} cancelled. Refund of ₹{b.refund:,} will be processed.", "success")
        except BookingError as e:
            flash(str(e), "error")
        return redirect(url_for("manage"))

    return app


if __name__ == "__main__":
    create_app("bookings.json", "accounts.json").run(debug=True)
