"""
Smart College Canteen

Run locally with: python app.py

Demo administrator account (change the password before using this beyond a
classroom demonstration):
    Email: admin@smartcanteen.com
    Password: Admin@123
"""

import os
import sqlite3
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "canteen.db"
ORDER_STATUSES = ("Pending", "Preparing", "Ready", "Collected")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "smart-canteen-local-development-key-change-before-sharing"
)
app.config["DATABASE"] = str(DATABASE_PATH)


SEED_FOODS = (
    (
        "Veg Burger",
        "Crispy vegetable patty, fresh lettuce, and our signature house sauce.",
        89,
        "Snacks",
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=85",
    ),
    (
        "Veg Sandwich",
        "Toasted garden-fresh vegetables with cheese and a herbed spread.",
        69,
     "Snacks",
     "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=900&q=85",
),
(
     "Cheese Pizza",
     "Golden, cheesy personal pizza finished with basil and tomato.",
     129,
     "Meals",
     "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=900&q=85",
),
(
     "Samosa",
     "Golden pastry filled with spiced potato, served with chutney.",
     25,
     "Snacks",
     "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=85",
),
(
     "Masala Maggi",
     "A comforting bowl of noodles tossed with vegetables and spices.",
     59,
     "Meals",
     "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=900&q=85",
),
(
     "Cold Coffee",
     "Chilled, creamy coffee blended fresh and topped with a light foam.",
     79,
     "Drinks",
     "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=900&q=85",
),
(
     "Fresh Lime Soda",
     "A sparkling lime cooler, made to order with a hint of mint.",
     49,
     "Drinks",
     "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=900&q=85",
),
(
     "Mango Shake",
     "A thick seasonal mango shake blended with chilled milk.",
     89,
     "Drinks",
     "https://images.unsplash.com/photo-1525385133512-2f3bdd039054?auto=format&fit=crop&w=900&q=85",
),
(
     "Chocolate Shake",
     "A rich chocolate milkshake made with cocoa and cold milk.",
     99,
     "Drinks",
     "https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=900&q=85",
),
(
     "Tea",
     "Freshly brewed Indian chai with a warming blend of spices.",
     20,
     "Drinks",
     "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=900&q=85",
    ),
)


def get_db():
    """Return this request's SQLite connection, opening it when needed."""
    if "db" not in g:
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    """Create the database, tables, starter menu, and demonstration admin."""
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student'
                    CHECK (role IN ('student', 'admin'))
            );

            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL CHECK (price >= 0),
                category TEXT NOT NULL,
                image TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total REAL NOT NULL CHECK (total >= 0),
                token TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (status IN ('Pending', 'Preparing', 'Ready', 'Collected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id INTEGER NOT NULL,
                  food_name TEXT NOT NULL,
                  price REAL NOT NULL CHECK (price >= 0),
                  quantity INTEGER NOT NULL CHECK (quantity > 0),
                  FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            );
            """
        )

        food_count = connection.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
        if food_count == 0:
            connection.executemany(
                """
                INSERT INTO foods (name, description, price, category, image)
                VALUES (?, ?, ?, ?, ?)
                """,
                SEED_FOODS,
            )

        admin_email = "admin@smartcanteen.com"
        admin_exists = connection.execute(
            "SELECT id FROM users WHERE email = ?", (admin_email,)
        ).fetchone()
        if admin_exists is None:
            connection.execute(
                """
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, 'admin')
                """,
                (
                     "Canteen Admin",
                     admin_email,
                     generate_password_hash("Admin@123"),
                ),
            )


def safe_next_url(candidate):
    """Accept only a same-site path as a post-login redirect."""
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            if request.is_json:
                return jsonify(
                    {
                        "error": "Please log in before placing an order.",
                        "login_url": url_for("login", next=url_for("index")),
                    }
                ), 401
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def get_order_items(order_ids):
    """Load item rows for several orders in one parameterized query."""
    if not order_ids:
        return {}
    placeholders = ",".join("?" for _ in order_ids)
    rows = get_db().execute(
        f"""
        SELECT order_id, food_name, price, quantity
        FROM order_items
        WHERE order_id IN ({placeholders})
        ORDER BY id
        """,
        tuple(order_ids),
    ).fetchall()
    grouped = {order_id: [] for order_id in order_ids}
    for row in rows:
        grouped[row["order_id"]].append(row)
    return grouped


@app.route("/")
def index():
    foods = get_db().execute(
        "SELECT id, name, description, price, category, image FROM foods ORDER BY id"
    ).fetchall()
    return render_template("index.html", foods=foods)


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("Please complete every field.", "error")
        elif len(name) > 100 or len(email) > 254:
            flash("Please use a shorter name or email address.", "error")
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        else:
            try:
                cursor = get_db().execute(
                    """
                    INSERT INTO users (name, email, password, role)
                    VALUES (?, ?, ?, 'student')
                    """,
                    (name, email, generate_password_hash(password)),
                )
                get_db().commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                session["name"] = name
                session["email"] = email
                session["role"] = "student"
                flash("Your student account is ready. Welcome!", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                get_db().rollback()
                flash("An account with that email already exists.", "error")

    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    next_url = safe_next_url(request.values.get("next"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
             "SELECT id, name, email, password, role FROM users WHERE email = ?",
             (email,),
        ).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("The email or password is incorrect. Please try again.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name'].split()[0]}.", "success")
            return redirect(next_url or url_for("index"))

    return render_template("login.html", next_url=next_url or "")


@app.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/place_order", methods=("POST",))
@login_required
def place_order():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return jsonify({"error": "Your cart could not be read. Please try again."}), 400

    quantities = {}
    for item in payload["items"]:
        if not isinstance(item, dict):
             return jsonify({"error": "The cart contains an invalid item."}), 400
        food_id = item.get("food_id")
        quantity = item.get("quantity")
        if (
             isinstance(food_id, bool)
             or not isinstance(food_id, int)
             or isinstance(quantity, bool)
             or not isinstance(quantity, int)
             or quantity < 1
             or quantity > 99
        ):
             return jsonify({"error": "The cart contains an invalid quantity."}), 400
        quantities[food_id] = quantities.get(food_id, 0) + quantity
        if quantities[food_id] > 99:
             return jsonify({"error": "A food quantity cannot exceed 99."}), 400

    if not quantities:
        return jsonify({"error": "Add at least one item before placing your order."}), 400

    food_ids = list(quantities)
    placeholders = ",".join("?" for _ in food_ids)
    foods = get_db().execute(
        f"""
        SELECT id, name, price
        FROM foods
        WHERE id IN ({placeholders})
        """,
        tuple(food_ids),
    ).fetchall()
    food_by_id = {food["id"]: food for food in foods}
    if len(food_by_id) != len(food_ids):
        return jsonify({"error": "One or more menu items are no longer available."}), 400

    total = round(
        sum(float(food_by_id[food_id]["price"]) * quantity for food_id, quantity in quantities.items()),
        2,
    )

    try:
        connection = get_db()
        cursor = connection.execute(
               """
               INSERT INTO orders (user_id, total, token, status)
               VALUES (?, ?, NULL, 'Pending')
            """,
            (session["user_id"], total),
        )
        order_id = cursor.lastrowid
        token = f"C{order_id + 100:03d}"
        connection.execute(
            "UPDATE orders SET token = ? WHERE id = ?", (token, order_id)
        )
        connection.executemany(
            """
            INSERT INTO order_items (order_id, food_name, price, quantity)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    order_id,
                    food_by_id[food_id]["name"],
                    food_by_id[food_id]["price"],
                    quantity,
                )
                for food_id, quantity in quantities.items()
            ],
        )
        connection.commit()
    except sqlite3.Error:
        get_db().rollback()
        app.logger.exception("Could not save an order")
        return jsonify({"error": "We could not save your order. Please try again."}), 500

    return jsonify({"redirect_url": url_for("token", order_id=order_id), "token": token}), 201


@app.route("/token/<int:order_id>")
@login_required
def token(order_id):
    if session.get("role") == "admin":
        order = get_db().execute(
            """
            SELECT orders.*, users.name AS student_name
            FROM orders JOIN users ON users.id = orders.user_id
            WHERE orders.id = ?
            """,
            (order_id,),
        ).fetchone()
    else:
        order = get_db().execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?",
            (order_id, session["user_id"]),
        ).fetchone()
    if order is None:
        abort(404)
    items = get_order_items([order_id])[order_id]
    return render_template("token.html", order=order, items=items)


@app.route("/orders")
@login_required
def orders():
    user_orders = get_db().execute(
        """
        SELECT id, total, token, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    items_by_order = get_order_items([order["id"] for order in user_orders])
    return render_template(
        "orders.html", orders=user_orders, items_by_order=items_by_order
    )


@app.route("/admin")
@admin_required
def admin():
    all_orders = get_db().execute(
        """
        SELECT orders.id, orders.total, orders.token, orders.status,
                orders.created_at, users.name AS student_name, users.email
        FROM orders JOIN users ON users.id = orders.user_id
        ORDER BY orders.id DESC
        """
    ).fetchall()
    items_by_order = get_order_items([order["id"] for order in all_orders])
    return render_template(
        "admin.html",
        orders=all_orders,
        items_by_order=items_by_order,
        statuses=ORDER_STATUSES,
    )


@app.route("/admin/orders/<int:order_id>/status", methods=("POST",))
@admin_required
def update_order_status(order_id):
    new_status = request.form.get("status", "")
    if new_status not in ORDER_STATUSES:
        flash("Choose a valid order status.", "error")
        return redirect(url_for("admin"))

    cursor = get_db().execute(
        "UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id)
    )
    get_db().commit()
    if cursor.rowcount == 0:
        abort(404)
    flash(f"Order status updated to {new_status}.", "success")
    return redirect(url_for("admin"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template(
        "login.html",
        next_url="",
        access_error="This page is only available to canteen administrators.",
    ), 403


@app.errorhandler(404)
def not_found(_error):
    return (
        render_template(
             "login.html",
             next_url="",
             access_error="We could not find that page or order.",
        ),
        404,
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
