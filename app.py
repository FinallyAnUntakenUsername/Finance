import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    stocks = db.execute("SELECT * FROM my_stocks WHERE user_id = ?", session["user_id"])

    return render_template("index.html", stocks=stocks)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        if lookup(request.form.get("symbol")) == None:
            return apology("Stock doesn't exist")
        elif not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("Sorry, but you should buy at least 1")
        else:
            stock = lookup(request.form.get("symbol"))
            rows = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
            row = rows[0]
            amount =  int(request.form.get("shares"))
            purchase = stock["price"] * amount
            if row["cash"] < purchase:
                return apology("Sorry, but the purchase is too big for your purse")
            else:
                left = row["cash"] - purchase
                left = round(left, 2)
                db.execute("INSERT INTO purchases (user_id, symbol, price, amount, total) VALUES(?, ?, ?, ?, ?)", session["user_id"], stock["symbol"], stock["price"], amount, purchase)
                db.execute("UPDATE users SET cash = ? WHERE id = ?", left, session["user_id"])

                purchases = db.execute("SELECT * FROM purchases WHERE user_id=?", session["user_id"])

                for purchase in purchases:
                    if not db.execute("SELECT * FROM my_stocks WHERE user_id = ? and symbol = ?", session["user_id"], stock["symbol"]):
                        db.execute("INSERT INTO my_stocks (user_id, symbol, price, amount, total) SELECT user_id, symbol, price, amount, total FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])
                    else:
                        stocks = db.execute("SELECT * FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])
                        p = 0
                        a = 0
                        t = 0
                        i = 0
                        for s in stocks:
                            p = p + s["price"]
                            a = a + s["amount"]
                            t = t + s["total"]
                            i = i + 1
                        p = round(p / i, 2)
                        t = round(t, 2)
                        db.execute("UPDATE my_stocks SET price = ?, amount = ?, total = ? WHERE symbol = ? AND user_id = ?", p, a, t, stock["symbol"], session["user_id"])
            message = "Go to index to see your stock(s)"
            return render_template("buy.html", message=message)



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
    return render_template("history.html", stocks=stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        if lookup(request.form.get("symbol")) == None:
            return apology("Sorry, but the stock doesn't exist")
        else:
            stock = lookup(request.form.get("symbol"))
            return render_template("quoted.html", stock=stock)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Please fill out the form")
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords doesn't match")
        elif db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")) != None:
            return apology("Sorry, username already taken")
        else:
            hashed = generate_password_hash(request.form.get("password"))

            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), hashed)

            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

            session["user_id"] = rows[0]["id"]

            return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT symbol FROM my_stocks WHERE user_id = ?", session["user_id"])

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)
    else:
        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("Sorry, you should sell at least 1")
        i = 0
        for stock in stocks:
            if request.form.get("symbol") == stock["symbol"]:
                i = 1
                purchase = lookup(request.form.get("symbol"))
                shares = int(request.form.get("shares"))
                total = purchase["price"] * shares
                total = round(total, 2)
                price = -purchase["price"]
                a = db.execute("SELECT * FROM my_stocks WHERE user_id = ? AND symbol = ?", session["user_id"], purchase["symbol"])
                my_stocks = a[0]
        if i != 1:
            return apology("Sorry, but you don't own that stock")
        elif my_stocks["amount"] < shares:
            return apology("Sorry, but you're trying to sell more shares than you have")
        else:
            db.execute("INSERT INTO purchases (symbol, price, amount, total, user_id) VALUES(?, ?, ?, ?, ?)", purchase["symbol"], price, shares, -total, session["user_id"])
            rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            row = rows[0]
            left = row["cash"] + total
            db.execute("UPDATE users SET cash = ? WHERE id = ?", left, session["user_id"])
            stock_left = my_stocks["amount"] - shares
            if stock_left == 0:
                db.execute("DELETE FROM my_stocks WHERE user_id = ? AND symbol = ?", session["user_id"], purchase["price"])
            else:
                end_price = my_stocks["total"] / my_stocks["amount"]
                end_total = end_price * stock_left
                end_price = round(end_price, 2)
                end_total = round(end_total, 2)
                db.execute("UPDATE my_stocks SET amount = ?, price = ?, total = ? WHERE user_id = ? AND symbol = ?", stock_left, end_price, end_total, session["user_id"], purchase["symbol"])

            return render_template("sell.html")

