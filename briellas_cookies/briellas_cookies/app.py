from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'briellas_secret_key_2024'

DB = 'briellas.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        contact TEXT NOT NULL,
        address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        cookie_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        total_price REAL NOT NULL,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )''')
    conn.commit()
    conn.close()

init_db()

COOKIES = {
    'smores': {
        'name': "S'mores Cookie",
        'price': 75,
        'desc': "A soft and chewy cookie inspired by the classic campfire treat. Made with rich chocolate, crushed graham crackers, and gooey marshmallows baked into every bite, this cookie delivers the perfect balance of sweetness and texture. Crispy on the edges and soft in the center, the S'mores Cookie is a comforting dessert that brings a warm, homemade flavor everyone will enjoy.",
        'emoji': '🔥',
        'tags': ['Bestseller', 'Fan Favorite']
    },
    'chocolate': {
        'name': 'Chocolate Cookie',
        'price': 65,
        'desc': 'A classic chocolate cookie baked to perfection with a soft, chewy center and rich chocolate flavor in every bite. Made with premium cocoa and loaded with chocolate chips, this cookie offers a deliciously sweet and satisfying treat. Perfect for dessert, snacks, or pairing with milk or coffee.',
        'emoji': '🍫',
        'tags': ['Classic', 'All-Time Fave']
    }
}

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

# Customer login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM customers WHERE email=?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('shop'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

# Customer register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        contact = request.form['contact'].strip()
        address = request.form['address'].strip()
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute('INSERT INTO customers (name,email,password,contact,address) VALUES (?,?,?,?,?)',
                         (name, email, hashed, contact, address))
            conn.commit()
            conn.close()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'error')
    return render_template('register.html')

# Customer shop
@app.route('/shop')
def shop():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    orders = conn.execute(
        'SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC LIMIT 5',
        (session['user_id'],)).fetchall()
    conn.close()
    return render_template('shop.html', cookies=COOKIES, orders=orders)

# Place order
@app.route('/order', methods=['POST'])
def order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cookie_type = request.form['cookie_type']
    quantity = int(request.form['quantity'])
    if cookie_type not in COOKIES or quantity < 1:
        flash('Invalid order.', 'error')
        return redirect(url_for('shop'))
    price = COOKIES[cookie_type]['price'] * quantity
    conn = get_db()
    conn.execute('INSERT INTO orders (customer_id,cookie_type,quantity,total_price) VALUES (?,?,?,?)',
                 (session['user_id'], cookie_type, quantity, price))
    conn.commit()
    conn.close()
    flash(f'Order placed! {quantity}x {COOKIES[cookie_type]["name"]} — ₱{price:.0f}', 'success')
    return redirect(url_for('shop'))

# Customer logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Admin ────────────────────────────────────────────────────────────────────

ADMIN_USER = 'AdminBriella'
ADMIN_PASS = '12345'

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Incorrect credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db()

    # Customers
    customers = conn.execute(
        'SELECT c.*, COUNT(o.id) as order_count FROM customers c LEFT JOIN orders o ON c.id=o.customer_id GROUP BY c.id ORDER BY c.created_at DESC'
    ).fetchall()

    # Weekly sales (last 7 days)
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    weekly = conn.execute(
        "SELECT cookie_type, SUM(quantity) as total_qty, SUM(total_price) as total_rev FROM orders WHERE created_at >= ? GROUP BY cookie_type",
        (week_ago,)).fetchall()

    # Recent orders with customer info
    recent_orders = conn.execute(
        'SELECT o.*, c.name, c.contact, c.address, c.email FROM orders o JOIN customers c ON o.customer_id=c.id ORDER BY o.created_at DESC LIMIT 20'
    ).fetchall()

    # Daily sales for the past 7 days
    daily_sales = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        row = conn.execute(
            "SELECT SUM(quantity) as qty FROM orders WHERE DATE(created_at)=?", (day,)
        ).fetchone()
        daily_sales.append({'date': day, 'qty': row['qty'] or 0})

    conn.close()
    return render_template('admin_dashboard.html',
                           customers=customers,
                           weekly=weekly,
                           recent_orders=recent_orders,
                           daily_sales=json.dumps(daily_sales),
                           cookies=COOKIES)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(debug=True)
