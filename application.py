import os

from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")
#pk_b67e5a475d8949cd8fd1be6f2b4946ee


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT symbol, name, SUM(shares) AS shares, price FROM history WHERE user_id=? GROUP BY symbol;", session["user_id"])
    total = 0
    price = {}
    for row in rows:
        result = lookup(row["symbol"])
        price[row["symbol"]] = result["price"]
        total += row["shares"] * result["price"]
    acc = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
    return render_template("index.html", rows=rows, cash=acc[0]["cash"], total=total, price=price, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        shares = request.form.get("shares")
        result = lookup(request.form.get("symbol"))
        if result is None:
            return render_template("buy.html", buyerr="Invalid symbol!")
        rows = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        cash = rows[0]["cash"]
        price = result["price"]
        cost = price * float(shares)
        if cash < cost:
            return render_template("buy.html", message="You don't have enough cash!")
        #Time Now
        now = datetime.now()
        db.execute("UPDATE users SET cash=:balance WHERE id=:uid", balance=(cash - cost), uid=session["user_id"])
        db.execute("INSERT INTO history (user_id, name, symbol, shares, price, time) VALUES (:user_id, :name, :symbol, :shares, :price, :time)", user_id=session["user_id"], name=result["name"], symbol=request.form.get("symbol"), shares=shares, price=price, time=now.strftime("%Y-%m-%d %H:%M:%S"))
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM history WHERE user_id=:uid ORDER BY time DESC;", uid=session["user_id"])
    return render_template("history.html", rows=rows, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def password():
    # """Change Password"""
    if request.method == "GET":
        return render_template("change-password.html")
    else:
        rows = db.execute("SELECT hash FROM users WHERE id=?", session["user_id"])
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")
        if not check_password_hash(rows[0]["hash"], request.form.get("current")):
            return apology("Password is incorrect!")
        elif not password or password != password_confirmation:
            return apology("Passwords doesn't match!")
        db.execute("UPDATE users SET hash=:hashpass WHERE id=:uid;", hashpass=generate_password_hash(password), uid=session["user_id"])
        return redirect("/logout")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("quote")
        result = lookup(symbol)
        if result is None:
            return render_template("quote.html", symbolerr="Invalid symbol!")
        return render_template("quoted.html", name=result["name"], price=result["price"], symbol=result["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        if not username:
            return render_template("apology.html", message="You must provide a username.")
        if len(db.execute("SELECT username FROM users WHERE username=?", username)) == 1:
            return render_template("register.html", message="Username already exists!")
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")
        if not password or password != password_confirmation:
            return render_template("register.html", passerr="Passwords doesn't match!")
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashpass)", username=username, hashpass=generate_password_hash(password))
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT DISTINCT symbol FROM history WHERE user_id=?;", session["user_id"])
        return render_template("sell.html", symbols=rows)
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        result = lookup(symbol)
        acc_shares = db.execute("SELECT symbol, SUM(shares) AS shares FROM history WHERE user_id=:uid AND symbol=:symbol GROUP BY symbol;", uid=session["user_id"], symbol=symbol)
        if shares <= 0 or acc_shares[0]["shares"] < shares:
            return apology("No enough shares!")
        #Time Now
        now = datetime.now()
        db.execute("UPDATE users SET cash=cash+:balance WHERE id=:uid", balance=(shares * result["price"]), uid=session["user_id"])
        db.execute("INSERT INTO history (user_id, name, symbol, shares, price, time) VALUES (:user_id, :name, :symbol, :shares, :price, :time)", user_id=session["user_id"], name=result["name"], symbol=symbol, shares=(-shares), price=result["price"], time=now.strftime("%Y-%m-%d %H:%M:%S"))
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
