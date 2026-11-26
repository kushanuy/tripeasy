"""
test_tripeasy.py - test cases TC01 to TC40.   Run with:  python -m pytest -v
"""
from datetime import date, datetime, timedelta

import pytest

from app import create_app
from auth import AccountStore, NoAccountError
from booking import BookingError, BookingSystem, SEATS_PER_FLIGHT

TODAY = date(2026, 11, 22)
FUTURE = "2026-12-25"
PEOPLE = [("Rahul Sharma", 21, "Male")]
GOOD = dict(email="rahul@example.com", phone="9876543210")


@pytest.fixture
def system():
    return BookingSystem()          # no file, fresh data every test


def first_flight(system, o="Bengaluru", d="Delhi"):
    return system.search(o, d, FUTURE, 1, "Economy", today=TODAY)[0][0]


def book(system, people=PEOPLE, flight=None, **kw):
    flight = flight or first_flight(system)
    args = dict(GOOD, **kw)
    return system.create_booking(flight.flight_id, FUTURE, "Economy", people,
                                 args["email"], args["phone"], today=TODAY)


# ------------------------------------------------------------- SEARCH (TC01-TC06)
def test_tc01_search_valid_route_returns_flights(system):
    results = system.search("Bengaluru", "Delhi", FUTURE, 1, "Economy", today=TODAY)
    assert len(results) == 5
    assert all(f.origin == "Bengaluru" and f.destination == "Delhi" for f, _, _ in results)


def test_tc02_results_sorted_cheapest_first(system):
    prices = [p for _, _, p in system.search("Mumbai", "Chennai", FUTURE, 1, "Economy", today=TODAY)]
    assert prices == sorted(prices)


def test_tc03_same_origin_and_destination_rejected(system):
    with pytest.raises(BookingError, match="cannot be the same"):
        system.search("Delhi", "Delhi", FUTURE, 1, "Economy", today=TODAY)


def test_tc04_past_date_rejected(system):
    with pytest.raises(BookingError, match="past"):
        system.search("Delhi", "Mumbai", "2026-11-01", 1, "Economy", today=TODAY)


@pytest.mark.parametrize("n", [0, 7, "abc"])
def test_tc05_invalid_traveller_count_rejected(system, n):
    with pytest.raises(BookingError):
        system.search("Delhi", "Mumbai", FUTURE, n, "Economy", today=TODAY)


def test_tc06_business_class_costs_more_than_economy(system):
    eco = system.search("Delhi", "Mumbai", FUTURE, 1, "Economy", today=TODAY)[0][2]
    biz = system.search("Delhi", "Mumbai", FUTURE, 1, "Business", today=TODAY)[0][2]
    assert biz > eco


# ----------------------------------------------------------- BOOKING (TC07-TC13)
def test_tc07_valid_booking_is_confirmed_with_pnr(system):
    b = book(system)
    assert b.status == "CONFIRMED" and len(b.pnr) == 6


def test_tc08_total_fare_is_price_times_passengers(system):
    f = first_flight(system)
    b = book(system, people=[("Asha Rao", 30, "Female"), ("Ravi Rao", 8, "Male")], flight=f)
    assert b.total_fare == f.price_for("Economy") * 2


def test_tc09_booking_reduces_seats_left(system):
    f = first_flight(system)
    book(system, people=[("Asha Rao", 30, "Female"), ("Ravi Rao", 8, "Male")], flight=f)
    assert system.seats_left(f.flight_id, FUTURE) == SEATS_PER_FLIGHT - 2


def test_tc10_cannot_book_more_seats_than_available(system):
    f = first_flight(system)
    for _ in range(SEATS_PER_FLIGHT // 5):                      # fill with groups of 5
        book(system, people=[(f"Person {c}", 20, "Male") for c in "ABCDE"], flight=f)
    assert system.seats_left(f.flight_id, FUTURE) == 0
    with pytest.raises(BookingError, match="not enough seats"):
        book(system, flight=f)


@pytest.mark.parametrize("name", ["", "R2D2", "A", "<script>"])
def test_tc11_invalid_passenger_name_rejected(system, name):
    with pytest.raises(BookingError):
        book(system, people=[(name, 20, "Male")])


@pytest.mark.parametrize("email", ["", "abc", "abc@", "a@b"])
def test_tc12_invalid_email_rejected(system, email):
    with pytest.raises(BookingError, match="email"):
        book(system, email=email)


@pytest.mark.parametrize("phone", ["12345", "1234567890", "98765abcde", ""])
def test_tc13_invalid_phone_rejected(system, phone):
    with pytest.raises(BookingError, match="Phone"):
        book(system, phone=phone)


# ----------------------------------------------------------- CANCEL (TC14-TC17)
def test_tc14_cancel_more_than_24h_gives_90_percent_refund(system):
    b = book(system)
    now = datetime(2026, 12, 1, 10, 0)
    c = system.cancel_booking(b.pnr, "rahul@example.com", now=now)
    assert c.status == "CANCELLED" and c.refund == round(b.total_fare * 0.9)


def test_tc15_cancel_within_24h_gives_50_percent_refund(system):
    b = book(system)
    dep = datetime.strptime(f"{FUTURE} {system.flights[b.flight_id].dep_time}", "%Y-%m-%d %H:%M")
    c = system.cancel_booking(b.pnr, "rahul@example.com", now=dep - timedelta(hours=5))
    assert c.refund == round(b.total_fare * 0.5)


def test_tc16_cancelling_frees_the_seats_and_cannot_repeat(system):
    f = first_flight(system)
    b = book(system, flight=f)
    system.cancel_booking(b.pnr, "rahul@example.com", now=datetime(2026, 12, 1))
    assert system.seats_left(f.flight_id, FUTURE) == SEATS_PER_FLIGHT
    with pytest.raises(BookingError, match="already cancelled"):
        system.cancel_booking(b.pnr, "rahul@example.com", now=datetime(2026, 12, 1))


def test_tc17_wrong_email_or_pnr_cannot_find_booking(system):
    b = book(system)
    with pytest.raises(BookingError, match="No booking found"):
        system.find_booking(b.pnr, "someone-else@example.com")
    with pytest.raises(BookingError, match="No booking found"):
        system.find_booking("ZZZZZZ", "rahul@example.com")


# ------------------------------------------------- WEBSITE + STORAGE (TC18-TC20)
@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "bookings.json"), str(tmp_path / "accounts.json"))
    app.config["TESTING"] = True
    return app.test_client()


def test_tc18_home_page_loads_with_search_form(client):
    r = client.get("/")
    assert r.status_code == 200 and b"SEARCH" in r.data and b"Bengaluru" in r.data


def test_tc19_full_website_booking_flow(client):
    client.post("/login", data=dict(email="kushanuy@gmail.com", password="abcd12345"))
    day = (date.today() + timedelta(days=10)).isoformat()
    r = client.get(f"/search?origin=Bengaluru&destination=Delhi&date={day}&travellers=1&cabin=Economy")
    assert r.status_code == 200 and b"BOOK NOW" in r.data
    fid = r.data.decode().split("/book/")[1].split("?")[0]

    r = client.post(f"/book/{fid}", data=dict(date=day, cabin="Economy", travellers=1,
                    name0="Kushanu Y", age0=20, gender0="Male",
                    email="kushanuy@gmail.com", phone="9876543210"), follow_redirects=True)
    assert b"Booking Confirmed" in r.data and b"Kushanu Y" in r.data


def test_tc20_bookings_survive_restart(tmp_path):
    path = str(tmp_path / "bookings.json")
    s1 = BookingSystem(path)
    b = book(s1)
    s2 = BookingSystem(path)                        # "restart" the app
    assert s2.find_booking(b.pnr, "rahul@example.com").total_fare == b.total_fare


# ------------------------------------------------- ACCOUNTS / LOGIN (TC21-TC27)
NEW_USER = dict(name="Asha Rao", age=30, gender="Female", email="asha@example.com",
                phone="9123456780", password="strongpass1")


def test_tc21_hardcoded_account_correct_password_allowed():
    assert AccountStore().authenticate("kushanuy@gmail.com", "abcd12345") == "kushanuy@gmail.com"


def test_tc22_hardcoded_account_wrong_password_rejected():
    store = AccountStore()
    with pytest.raises(BookingError, match="Incorrect password"):
        store.authenticate("kushanuy@gmail.com", "wrong-pass")
    with pytest.raises(BookingError, match="Incorrect password"):
        store.authenticate("KushAnuy@Gmail.com", "ABCD12345")   # email ignores case, password does not


def test_tc23_unknown_email_is_told_to_create_account():
    with pytest.raises(NoAccountError, match="create an account"):
        AccountStore().authenticate("random@example.com", "whatever1")


def test_tc24_signup_then_login_works_and_profile_is_saved():
    store = AccountStore()
    store.signup(**NEW_USER)
    assert store.authenticate("asha@example.com", "strongpass1") == "asha@example.com"
    prof = store.get("asha@example.com")
    assert prof["name"] == "Asha Rao" and prof["phone"] == "9123456780" and "password_hash" not in prof


@pytest.mark.parametrize("change, message", [
    (dict(email="kushanuy@gmail.com"), "already exists"),       # cannot take the hard-coded account
    (dict(password="short"), "at least 8"),
    (dict(phone="12345"), "Phone"),
    (dict(email="not-an-email"), "email"),
    (dict(name="R2D2"), "Invalid passenger name"),
])
def test_tc25_invalid_signup_rejected(change, message):
    with pytest.raises(BookingError, match=message):
        AccountStore().signup(**dict(NEW_USER, **change))


def test_tc26_new_accounts_survive_restart_and_password_not_stored_in_plain_text(tmp_path):
    path = str(tmp_path / "accounts.json")
    AccountStore(path).signup(**NEW_USER)
    assert "strongpass1" not in open(path).read()
    assert AccountStore(path).authenticate("asha@example.com", "strongpass1")


def test_tc27_cannot_sign_up_twice_with_same_email():
    store = AccountStore()
    store.signup(**NEW_USER)
    with pytest.raises(BookingError, match="already exists"):
        store.signup(**NEW_USER)


# --------------------------------------------- LOGIN DURING BOOKING, WEBSITE (TC28-TC34)
BOOK_URL = "/book/6E101?date=2026-12-25&travellers=2&cabin=Economy"


def login(client, email="kushanuy@gmail.com", password="abcd12345", next_url=BOOK_URL):
    return client.post("/login", data=dict(email=email, password=password, next=next_url),
                       follow_redirects=True)


def test_tc28_booking_page_needs_login(client):
    r = client.get(BOOK_URL)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.get("/manage").status_code == 302


def test_tc29_login_returns_to_booking_and_autofills_saved_details(client):
    html = login(client).data.decode()
    assert "Kushanu Y" in html and "9876543210" in html and "kushanuy@gmail.com" in html
    assert 'value="20"' in html                      # age
    assert html.count('name="name') == 2             # 2 travellers -> only first one is filled
    assert html.count('value="Kushanu Y"') == 1


def test_tc30_wrong_password_on_website_stays_logged_out(client):
    r = client.post("/login", data=dict(email="kushanuy@gmail.com", password="nope"))
    assert b"Incorrect password" in r.data
    assert client.get("/manage").status_code == 302


def test_tc31_unknown_email_on_website_is_prompted_to_create_account(client):
    r = login(client, email="someone@example.com", password="whatever1")
    assert b"create an account" in r.data and b"/signup" in r.data
    assert client.get("/manage").status_code == 302


def test_tc32_signup_on_website_logs_in_and_autofills_booking(client):
    r = client.post("/signup", data=dict(NEW_USER, next=BOOK_URL), follow_redirects=True)
    html = r.data.decode()
    assert "Account created" in html and "Asha Rao" in html and "9123456780" in html
    assert "asha@example.com" in html


def test_tc33_booking_is_always_linked_to_logged_in_email(client):
    login(client)
    day = (date.today() + timedelta(days=10)).isoformat()
    r = client.post("/book/6E101", data=dict(date=day, cabin="Economy", travellers=1,
                    name0="Kushanu Y", age0=20, gender0="Male",
                    email="other.person@example.com", phone="9876543210"))       # tampered email
    pnr = r.headers["Location"].rsplit("/", 1)[1]
    system = client.application.config["SYSTEM"]
    assert system.bookings[pnr].email == "kushanuy@gmail.com"


def test_tc34_logout_blocks_booking_again(client):
    login(client)
    r = client.get("/logout", follow_redirects=True)
    assert b"logged out" in r.data and b"Login" in r.data
    assert client.get("/manage").status_code == 302


def test_tc35_login_cannot_redirect_to_other_websites(client):
    r = client.post("/login", data=dict(email="kushanuy@gmail.com", password="abcd12345",
                                        next="https://another-site.com"))
    assert r.status_code == 302 and "another-site.com" not in r.headers["Location"]


# ------------------------------------------------- EXTRA CHECKS (TC36-TC40)
@pytest.mark.parametrize("age, gender", [(130, "Male"), (-1, "Male"), ("ten", "Male"), (20, "Robot")])
def test_tc36_invalid_age_or_gender_rejected(system, age, gender):
    with pytest.raises(BookingError):
        book(system, people=[("Asha Rao", age, gender)])


def test_tc37_cannot_cancel_after_departure(system):
    b = book(system)
    dep = system.departure(b.flight_id, FUTURE)
    with pytest.raises(BookingError, match="already departed"):
        system.cancel_booking(b.pnr, "rahul@example.com", now=dep + timedelta(minutes=1))


def test_tc38_flights_that_already_left_today_are_hidden_and_cannot_be_booked(system):
    today = date(2026, 12, 25)
    now = datetime(2026, 12, 25, 12, 0)                    # midday
    results = system.search("Bengaluru", "Delhi", FUTURE, 1, "Economy", today=today, now=now)
    assert results and all(f.dep_time > "12:00" for f, _, _ in results)
    morning = next(f for f in system.flights.values()
                   if f.origin == "Bengaluru" and f.destination == "Delhi" and f.dep_time < "12:00")
    with pytest.raises(BookingError, match="already departed"):
        system.create_booking(morning.flight_id, FUTURE, "Economy", PEOPLE,
                              GOOD["email"], GOOD["phone"], today=today, now=now)


@pytest.mark.parametrize("travellers", ["abc", "", "0", "100"])
def test_tc39_edited_traveller_count_shows_error_not_crash(client, travellers):
    login(client)
    day = (date.today() + timedelta(days=10)).isoformat()
    r = client.post("/book/6E101", data=dict(date=day, cabin="Economy", travellers=travellers,
                    name0="Kushanu Y", age0=20, gender0="Male", phone="9876543210"),
                    follow_redirects=True)
    assert r.status_code == 200 and b"1 to 6 travellers" in r.data


def test_tc40_confirmation_page_only_visible_to_its_owner(client):
    login(client)
    day = (date.today() + timedelta(days=10)).isoformat()
    r = client.post("/book/6E101", data=dict(date=day, cabin="Economy", travellers=1,
                    name0="Kushanu Y", age0=20, gender0="Male", phone="9876543210"))
    url = r.headers["Location"]
    assert b"Booking Confirmed" in client.get(url).data       # owner can see it
    client.get("/logout")
    assert client.get(url).status_code == 302                 # logged out -> sent to login
    client.post("/signup", data=NEW_USER)                     # a different user
    r = client.get(url, follow_redirects=True)
    assert b"Booking not found" in r.data and b"9876543210" not in r.data
