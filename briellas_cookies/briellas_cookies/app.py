from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'briellas_secret_key_2024')

# ── AIVEN MYSQL CREDENTIALS ──────────────────────────────────────────────────
DB_HOST = os.environ.get('DB_HOST', 'mysql-2d3a799-eac-0c42.e.aivencloud.com')
DB_PORT = int(os.environ.get('DB_PORT', 17968))
DB_USER = os.environ.get('DB_USER', 'avnadmin')
DB_PASS = os.environ.get('DB_PASS', 'AVNS_tZiyrWIXCkvcWL6bUj_')
DB_NAME = os.environ.get('DB_NAME', 'defaultdb')

def get_db():
    """Establishes a secure connection to your Aiven MySQL cluster."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        ssl={'ssl': {}},  # Enforces REQUIRED SSL encryption mode for Aiven connections
        cursorclass=DictCursor,  # Makes rows act like dictionaries to match HTML syntax
        autocommit=True
    )

def init_db():
    """Generates production tables inside MySQL if they do not exist."""
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            contact VARCHAR(100) NOT NULL,
            address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            cookie_type VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.close()

# Initialize database tables on start
init_db()

COOKIES = {
    'smores': {
        'name': "S'mores Cookie",
        'price': 75,
        'desc': "A soft and chewy cookie inspired by the classic campfire treat. Made with rich chocolate, crushed graham crackers, and gooey marshmallows baked into every bite.",
        'emoji': '🔥',
        'tags': ['Bestseller', 'Fan Favorite']
    },
    'chocolate': {
        'name': 'Chocolate Cookie',
        'price': 65,
        'desc': 'A classic chocolate cookie baked to perfection with a soft, chewy center and rich chocolate flavor in every bite.',
        'emoji': '🍫',
        'tags': ['Classic', 'All-Time Fave']
    }
}

# ── Customer Routes ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Safely checks for fields to prevent 400 Bad Request errors
        if 'email' not in request.form or 'password' not in request.form:
            flash('Invalid form submission.', 'error')
            return redirect(url_for('login'))

        email = request.form['email'].strip()
        password = request.form['password']
        
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM customers WHERE email = %s', (email,))
            user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('shop'))
        flash('Invalid email or password.', 'error')
    
    # FIX: Render your actual customer login interface, not the admin_login template
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        contact = request.form['contact'].strip()
        address = request.form['address'].strip()
        hashed = generate_password_hash(password)
        
        conn = get_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO customers (name, email, password, contact, address) VALUES (%s, %s, %s, %s, %s)',
                    (name, email, hashed, contact, address)
                )
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except pymysql.err.IntegrityError:
            flash('Email already registered.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/shop')
def shop():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM orders WHERE customer_id = %s ORDER BY created_at DESC LIMIT 5',
            (session['user_id'],)
        )
        orders = cursor.fetchall()
        
        for order in orders:
            if 'created_at' in order and isinstance(order['created_at'], datetime):
                order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                
    conn.close()
    return render_template('shop.html', cookies=COOKIES, orders=orders)

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
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO orders (customer_id, cookie_type, quantity, total_price) VALUES (%s, %s, %s, %s)',
            (session['user_id'], cookie_type, quantity, price)
        )
    conn.close()
    
    flash(f'Order placed! {quantity}x {COOKIES[cookie_type]["name"]} — ₱{price:.0f}', 'success')
    return redirect(url_for('shop'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Admin Routes ─────────────────────────────────────────────────────────────

ADMIN_USER = 'AdminBriella'
ADMIN_PASS = '12345'

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if 'username' not in request.form or 'password' not in request.form:
            flash('Invalid admin form submission.', 'error')
            return redirect(url_for('admin_login'))

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
    with conn.cursor() as cursor:
        # Customers Mapping
        cursor.execute('''
            SELECT c.id, c.name, c.email, c.contact, c.address, c.created_at, COUNT(o.id) as order_count 
            FROM customers c LEFT JOIN orders o ON c.id = o.customer_id 
            GROUP BY c.id, c.name, c.email, c.contact, c.address, c.created_at 
            ORDER BY c.created_at DESC
        ''')
        customers = cursor.fetchall()
        for c in customers:
            if isinstance(c['created_at'], datetime):
                c['created_at'] = c['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        # Weekly sales (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7))
        cursor.execute(
            "SELECT cookie_type, SUM(quantity) as total_qty, SUM(total_price) as total_rev FROM orders WHERE created_at >= %s GROUP BY cookie_type",
            (week_ago,)
        )
        weekly = cursor.fetchall()

        # Recent transactions listing
        cursor.execute('''
            SELECT o.*, c.name, c.contact, c.address, c.email 
            FROM orders o JOIN customers c ON o.customer_id = c.id 
            ORDER BY o.created_at DESC LIMIT 20
        ''')
        recent_orders = cursor.fetchall()
        for ro in recent_orders:
            if isinstance(ro['created_at'], datetime):
                ro['created_at'] = ro['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        # Daily sales compilation parsing for charts
        daily_sales = []
        for i in range(6, -1, -1):
            day_start = (datetime.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            cursor.execute(
                "SELECT SUM(quantity) as qty FROM orders WHERE created_at >= %s AND created_at < %s",
                (day_start, day_end)
            )
            row = cursor.fetchone()
            qty_val = int(row['qty']) if row and row['qty'] is not None else 0
            daily_sales.append({'date': day_start.strftime('%Y-%m-%d'), 'qty': qty_val})

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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
