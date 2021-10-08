from functools import singledispatch
from helper import requires_access_level, vehicle_lookup
from logging import error
import psycopg2
from config import config
from user import ACCESS, User, ZONE
from datetime import datetime, timedelta, time
import re

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialise Postgres Connection
def connect(sql, values = ""):
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)
		
        # create a cursor
        cur = conn.cursor()
        cur.execute(sql , values)
        # execute a statement
        conn.commit()

        # display the PostgreSQL database server version
        db_version = cur.fetchall()
        return db_version
        # print(db_version)
       
	# close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')

    # return db_version


if __name__ == '__main__':
    connect()

@app.route("/")
@requires_access_level(ACCESS['Customer'])
def index():
    return render_template("index.html")

@app.route("/register", methods = ["POST", "GET"])
def register():
    if request.method== "POST":
        # get form data
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        username = request.form.get("username")
        type = request.form.get("type")
        email_address = request.form.get("email_address")
        phone_number = request.form.get("phone_number")
        number = request.form.get("number")
        street = request.form.get("street")
        postcode = request.form.get("postcode")

        confirmation = request.form.get("confirmation")
        hashed = generate_password_hash(request.form.get("password"))

        if not hashed or not username or not first_name or not last_name or not type or not email_address or not phone_number or not number or not street or not postcode or not confirmation:
            return redirect("TODO.html")
        if not check_password_hash(hashed, confirmation):
            return redirect("TODO.html")

        # Check user does not already exist
        if connect("SELECT username FROM users WHERE username =  %s", (username,)):
            return redirect("TODO.html")
        # Enter user onto database
        else:
            connect("""INSERT INTO users 
                    (first_name, last_name, email_address, username, hashed, postcode, street, number, phone_number, type) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", (first_name, last_name, email_address, username, hashed, postcode, street, number, phone_number, type))
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    # forget user sessions
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("TODO.html")
        if not request.form.get("password"):
            return render_template("TODO.html")
            
        rows = connect("SELECT * FROM users WHERE username = %s;", (request.form.get("username"),))
        if len(rows) != 1 or not check_password_hash(rows[0][5], request.form.get("password")):
            return redirect("/login")

        # add user id and access level to session
        session["user_id"] = rows[0][0]
        session["access"] = ACCESS[rows[0][10]]

        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/logout", methods = ["GET","POST"])
@requires_access_level(ACCESS["Customer"])
def logout():
    session.clear()
    return redirect("/")

@app.route("/vehicle", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Customer"])
def vehicle():
    # find users vehicles
    vehicles = connect("SELECT * FROM vehicles WHERE owner_id = (%s);",  (session["user_id"],))
    # user can add vehicles
    if request.method == "POST":
        registration = request.form.get("registration")
        if not registration:
            return redirect("/vehicle")
        
        # search dvla API for inputted vehicle
        vehicle_detail = vehicle_lookup(registration)
        
        # if vehicle exists, add to database under current owner
        if not (vehicle_detail is None):
            print(vehicle_detail.get("make"))
            if not connect("SELECT registration FROM vehicles WHERE owner_id =  %s AND registration = %s", (session["user_id"], registration)):
                connect("""INSERT INTO vehicles (registration, owner_id, make, model, year, mot_date) 
                        VALUES (%s, %s, %s, %s, %s, %s);""", 
                        (registration, session["user_id"], vehicle_detail.get("make"), vehicle_detail.get("model"), vehicle_detail.get("year"), vehicle_detail.get("mot_date")))
                        
                # return render_template("vehicle_submit.html", vehicle_detail = vehicle_detail)
                return redirect("vehicle")
            else: 
                return redirect("/vehicle")
        else:
            return redirect("/vehicle")
    if request.method == "GET":
        return render_template("vehicle.html", vehicles = vehicles)

@app.route("/booking", methods = ["GET","POST"])
@requires_access_level(ACCESS["Customer"])
def booking():
    bookings = connect("""SELECT booking.job_id, vehicles.registration, vehicles.make, dealer.dealer_name, booking.day, booking.start_time, booking.end_time
                        FROM booking
                        JOIN vehicles ON booking.vehicle_id = vehicles.id
                        JOIN ramp ON booking.ramp_id = ramp.ramp_id
                        JOIN dealer ON ramp.dealer_code = dealer.dealer_code
                        WHERE booking.owner_id = %s AND booking.start_time >= %s AND booking.paid = %s""", (session["user_id"], datetime.now().time(), "False", )) 

    print(bookings) 
    if bookings is None:
        bookings = []
                                # 
                # WHERE booking.owner_id = %s""", (session["user_id"],)
    dealers = connect("SELECT dealer_name FROM dealer")
    vehicles = connect("SELECT registration, make FROM vehicles WHERE owner_id = %s", (session["user_id"],))
    if request.method == "POST":
        vehicle = request.form.get("vehicle")
        dealer = request.form.get("dealer")
        date =  request.form.get("date")
        dealer_code = connect("SELECT dealer_code, open_time, close_time FROM dealer WHERE dealer_name = %s", (dealer,))
        # times = connect("""SELECT DISTINCT availability.start_time, availability.end_time 
        #                 FROM availability
        #                 JOIN ramp 
        #                 ON ramp.ramp_id = availability.ramp_id
        #                 JOIN dealer 
        #                 ON ramp.dealer_code = dealer.dealer_code
        #                 WHERE ramp.dealer_code = %s AND availability.availability = %s AND availability.day = %s
        #                 AND availability.start_time > dealer.open_time AND availability.end_time < dealer.close_time AND availability.start_time > %s""", (dealer_code[0][0], "True", date, datetime.now().time() ,))
        times = connect("""SELECT DISTINCT availability.start_time, availability.end_time 
                        FROM availability
                        JOIN ramp ON ramp.ramp_id = availability.ramp_id
                        JOIN dealer ON ramp.dealer_code = dealer.dealer_code
                        WHERE ramp.dealer_code = %s AND availability.availability = %s AND availability.day = %s
                        AND availability.start_time > dealer.open_time AND availability.end_time < dealer.close_time AND availability.day > %s""",(dealer_code[0][0],"True", date,datetime.now().date(), ))
        print(dealer_code)
        print(vehicle)
        print(dealer)
        print(date)
        print(times)
        
        return render_template("bookings_dates.html", dealers = dealer, vehicles = vehicle, times= times, date = date)
    if request.method == "GET":
        return render_template("bookings.html", dealers = dealers, vehicles = vehicles, bookings= bookings)

@app.route("/booking_confirm", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Customer"])
def booking_confirm():
    if request.method == "POST":
        vehicle = request.form.get("vehicle").split(" |")[0]
        dealer = request.form.get("dealer")
        date =  request.form.get("date")
        start = request.form.get("start_time")

        dealer_code = connect("SELECT dealer_code FROM dealer WHERE dealer_name = %s", (dealer, ))[0][0]

        start_time = datetime.strptime(start, "%H:%M:%S").time()
        end_time = (datetime.strptime(start, "%H:%M:%S") + timedelta(hours = 1)).time()
        date = datetime.strptime(date, "%Y-%m-%d")

        vehicle_id = connect("SELECT id FROM vehicles WHERE registration = %s AND owner_id = %s", (vehicle, session["user_id"], ))[0][0]
        
        ramp = connect("""SELECT availability.ramp_id 
                        FROM availability 
                        JOIN ramp ON availability.ramp_id = ramp.ramp_id
                        WHERE availability.start_time = %s AND availability.day = %s AND availability.availability = %s AND ramp.dealer_code = %s
                        LIMIT 1 """, (start_time, date, "True", dealer_code, ))

        connect("""INSERT INTO booking (ramp_id, owner_id, vehicle_id, start_time, end_time, day, paid) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) """, (ramp[0][0], session['user_id'], vehicle_id, start_time, end_time, date, "False"))

        job_id = connect("""SELECT job_id 
                            FROM booking  
                            WHERE ramp_id = %s AND owner_id = %s AND vehicle_id = %s AND start_time = %s AND end_time = %s AND day = %s"""
                            , (ramp[0][0], session['user_id'], vehicle_id, start_time, end_time, date))

        connect("""UPDATE availability SET availability = %s, job_id = %s
                WHERE ramp_id = %s AND start_time = %s AND end_time = %s AND day = %s"""
                , ("False",job_id[0][0], ramp[0][0], start_time, end_time, date))

        return render_template("booking_confirmed.html", start_time = start_time, job_id = job_id[0][0], date = datetime.strftime(date, "%d/%m/%Y"))

    if request.method == "GET":
        return redirect("/booking")

@app.route("/new_dealer", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Manufacturer"])
def new_dealer():
    if request.method == "POST":
        dealer_name =request.form.get("dealer_name")
        zone = request.form.get("zone")
        region = request.form.get("region")
        number = request.form.get("number")
        street = request.form.get("street")
        postcode = request.form.get("postcode")
        open_time = request.form.get("open_time")
        close_time = request.form.get("close_time")
        labour_cost = request.form.get("labour_cost")
        
        if not dealer_name or not zone or not region or not number or not street or not postcode or not open_time or not close_time or not labour_cost:
            return redirect("TODO.html")

        # Check dealer does not already exist
        if connect("SELECT dealer_name FROM dealer WHERE dealer_name =  %s", (dealer_name,)):
            return redirect("TODO.html")
        # Enter user onto database
        else:
            connect("""INSERT INTO dealer 
                    (dealer_name, zone, region, postcode, street, number, open_time, close_time, labour_cost) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", (dealer_name, zone, region, postcode, street, number, open_time, close_time, labour_cost))


        return redirect("/")
    if request.method == "GET":
        return render_template("new_dealer.html", zone = ZONE)        

@app.route("/dealer", methods = ["GET"])
@requires_access_level(ACCESS["Manufacturer"])
def dealer():
    dealers = connect("SELECT * FROM dealer")
    return render_template("dealer.html", dealers = dealers)  

@app.route("/ramp", methods = ["POST", "GET"])
@requires_access_level(ACCESS["Dealer"])
def ramp():
    dealer_code = connect("SELECT dealer_code FROM users WHERE id = %s", (session["user_id"],))

    ramps = connect("SELECT * FROM ramp WHERE dealer_code = %s", (dealer_code[0],))
    if ramps is None:
        ramps = []

    if request.method == "POST":
        connect("""INSERT INTO ramp 
                (dealer_code) 
                VALUES (%s)""", (dealer_code[0],))
        return redirect("/ramp")
    
    if request.method == "GET":
        return render_template("ramps.html", ramps = ramps)   


@app.route("/user", methods = ["POST", "GET"])
@requires_access_level(ACCESS["Dealer"])
def user():
    dealers = connect("SELECT dealer_name FROM dealer")
    if request.method == "POST":
        dealer_name = request.form.get("dealer_name")
        dealer_code = connect("SELECT dealer_code FROM dealer WHERE dealer_name = %s", (dealer_name, ))
        print(dealer_code[0])
        connect("""UPDATE users SET dealer_code = %s 
                 WHERE id = %s""", (dealer_code[0], session["user_id"]))
        return  redirect("/user")

    if request.method == "GET":
        return render_template("user.html", dealers = dealers)       

@app.route("/view_bookings", methods = ["GET"])
@requires_access_level(ACCESS["Dealer"])
def view_bookings():
    dealer_code = connect("SELECT dealer_code FROM users WHERE id = %s", (session["user_id"],))
    bookings = connect("""SELECT booking.ramp_id, vehicles.registration, vehicles.make, users.first_name, users.last_name, booking.day, booking.start_time, booking.end_time
                        FROM booking
                        JOIN users ON booking.owner_id = users.id
                        JOIN vehicles ON booking.vehicle_id = vehicles.id
                        JOIN ramp ON booking.ramp_id = ramp.ramp_id
                        WHERE ramp.dealer_code = %s AND booking.paid = %s
                        """, (dealer_code[0][0],"False", ))

    if bookings is None:
        bookings = []

    if request.method == "GET":
        return render_template("dealer_bookings.html", bookings= bookings)

@app.route("/invoice", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Dealer"])
def invoice():
    dealer_code = connect("SELECT dealer_code FROM users WHERE id = %s", (session["user_id"],))
    bookings = connect("""SELECT booking.job_id, booking.ramp_id, vehicles.registration, vehicles.make, users.first_name, users.last_name, booking.day, booking.start_time, booking.end_time
                    FROM booking
                    JOIN users ON booking.owner_id = users.id
                    JOIN vehicles ON booking.vehicle_id = vehicles.id
                    JOIN ramp ON booking.ramp_id = ramp.ramp_id
                    WHERE ramp.dealer_code = %s AND booking.paid = %s
                    """, (dealer_code[0][0],"False",))
    if bookings is None:
        bookings = []

    paid = connect("""SELECT booking.job_id, vehicles.registration, vehicles.make, users.first_name, users.last_name, invoice.invoice_date, invoice.invoice_value
                    FROM booking
                    JOIN users ON booking.owner_id = users.id
                    JOIN vehicles ON booking.vehicle_id = vehicles.id
                    JOIN ramp ON booking.ramp_id = ramp.ramp_id
                    JOIN invoice ON booking.job_id = invoice.job_id
                    WHERE ramp.dealer_code = %s AND booking.paid = %s
                    """, (dealer_code[0][0],"True",))

    if paid is None:
        paid = []

    if request.method == "POST":
        booking = request.form.get("booking").split(" |")[0]
        hours = request.form.get("hours")
        if not hours:
            return redirect("/invoice")
        hours_rate = connect("SELECT labour_cost FROM dealer WHERE dealer_code = %s", (dealer_code[0][0], ))
        invoice_total = float(hours_rate[0][0]) * float(hours)

        connect("""INSERT INTO invoice(job_id, dealer_code, invoice_type, invoice_value, invoice_date)
                 VALUES (%s,%s,%s,%s,%s) """, (booking, dealer_code[0][0], "Hours", invoice_total, datetime.today()))
        connect("""UPDATE booking SET paid = %s 
                 WHERE job_id = %s""", ("True", booking))
        connect("""INSERT INTO customer_quality(completed, job_id, overall, speed, quality, submit_date) VALUES (%s, %s, %s, %s, %s, %s) """, ("False", booking, 0, 0, 0, datetime.today(), ))

        return redirect("/invoice")

    if request.method == "GET":
        return render_template("invoice.html", bookings = bookings, paid = paid)

@app.route("/customer_invoice", methods = ["GET"])
@requires_access_level(ACCESS["Customer"])
def customer_invoice():
    bookings = connect("""SELECT booking.job_id, booking.ramp_id, vehicles.registration, vehicles.make, users.first_name, users.last_name, booking.day, booking.start_time, booking.end_time
                FROM booking
                JOIN users ON booking.owner_id = users.id
                JOIN vehicles ON booking.vehicle_id = vehicles.id
                JOIN ramp ON booking.ramp_id = ramp.ramp_id
                WHERE users.id = %s AND booking.paid = %s
                """, (session["user_id"],"False",))

    paid = connect("""SELECT booking.job_id, vehicles.registration, vehicles.make, invoice.invoice_date, invoice.invoice_value
                    FROM booking
                    JOIN users ON booking.owner_id = users.id
                    JOIN vehicles ON booking.vehicle_id = vehicles.id
                    JOIN ramp ON booking.ramp_id = ramp.ramp_id
                    JOIN invoice ON booking.job_id = invoice.job_id
                    WHERE users.id = %s AND booking.paid = %s
                    """, (session["user_id"],"True",))

    if request.method == "GET":
        return render_template("customer_invoices.html", bookings=bookings, paid = paid)

@app.route("/quality", methods = ["POST", "GET"])
@requires_access_level(ACCESS["Customer"])
def quality():
    unanswered = connect("""SELECT customer_quality.job_id, booking.day, vehicles.registration, vehicles.make
                            FROM customer_quality 
                            JOIN invoice ON customer_quality.job_id = invoice.job_id
                            JOIN booking ON booking.job_id = customer_quality.job_id 
                            JOIN vehicles ON booking.vehicle_id = vehicles.id
                            WHERE booking.owner_id = %s AND customer_quality.completed = %s """, (session["user_id"], "False", )) 

    if request.method == "POST":
        booking = request.form.get("booking").split(" |")[0]
        overall = request.form.get("overall")
        speed = request.form.get("speed")
        quality = request.form.get("quality")

        if booking == "Select Booking" or overall == "Overall Satifaction" or speed == "Ease of Booking" or quality == "Quality of Work Carried Out":
            return redirect("/quality")

        connect("""UPDATE customer_quality SET overall = %s, speed = %s, quality = %s, submit_date = %s, completed = %s
                 WHERE job_id = %s""", (overall, speed, quality, datetime.today(), "True", booking))

        return render_template("feedback.html")

    if request.method == "GET":
        return render_template("quality_customer.html", bookings = unanswered)

@app.route("/view_feedback", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Dealer"])
def view_feedback():
    dealer_code = connect("SELECT dealer_code FROM users WHERE id = %s", (session["user_id"],))[0][0]

    feedbacks =  connect("""SELECT customer_quality.job_id, users.first_name, users.last_name,  users.phone_number, vehicles.make, vehicles.registration, 
                            customer_quality.overall, customer_quality.speed, customer_quality.quality, customer_quality.submit_date
                            FROM customer_quality 
                            JOIN booking ON customer_quality.job_id = booking.job_id
                            JOIN users ON booking.owner_id = users.id
                            JOIN vehicles ON booking.vehicle_id = vehicles.id
                            JOIN invoice ON booking.job_id = invoice.job_id
                            WHERE invoice.dealer_code = %s""", (dealer_code,))
    if request.method=="GET":
        return render_template("view_feedback.html", feedbacks = feedbacks)

@app.route("/password", methods=["GET", "POST"])
@requires_access_level(ACCESS["Customer"])
def change_password():
    if request.method == "POST":
        confirmation = request.form.get("confirmation")
        hashed = generate_password_hash(request.form.get("password"))
        username = request.form.get("username")

        # Check for correct user inputs
        if not hashed:
            return redirect("/password")
        if not confirmation:
            return redirect("/password")
        if not username:
            return redirect("/password")
        if not check_password_hash(hashed, confirmation):
            return redirect("/password")

        # Enter user onto database
        connect("UPDATE users SET hashed = %s WHERE id = %s", (hashed, session["user_id"]))
        return redirect("/")
    return render_template("password.html")

@app.route("/dealer_info", methods = ["GET", "POST"])
@requires_access_level(ACCESS["Dealer"])
def dealer_info():
    dealer_info = connect("""SELECT dealer.* 
                            FROM dealer
                            JOIN users ON users.dealer_code = dealer.dealer_code
                            WHERE users.id = %s """, (session["user_id"],))
    dealer_code = dealer_info[0][0]
    print(dealer_code)

    if request.method == "POST":
        number = request.form.get("number")
        street = request.form.get("street")
        postcode = request.form.get("postcode")
        open_time = request.form.get("open_time")
        close_time = request.form.get("close_time")
        labour_cost = request.form.get("labour_cost")

        connect("""UPDATE dealer 
                    SET number = %s, street = %s, postcode = %s, open_time = %s, close_time = %s, labour_cost = %s
                    WHERE dealer_code = %s""", (number, street, postcode, open_time, close_time, labour_cost, dealer_code))

        return redirect("/dealer_info")

    if request.method == "GET":
        return render_template("dealer_info.html", dealer_info = dealer_info)