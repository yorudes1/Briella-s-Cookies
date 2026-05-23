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
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        ssl={'ssl': {}},
        cursorclass=DictCursor,
        autocommit=True
    )

def init_db():
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
        
        cursor.execute("SHOW COLUMNS FROM orders LIKE 'delivery_date'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_date VARCHAR(100) DEFAULT 'Not Scheduled Yet'")
    conn.close()

init_db()

COOKIES = {
    'smores': {
        'name': "S'mores Cookie",
        'price': 75,
        'desc': "A soft and chewy cookie inspired by the classic campfire treat.",
        'emoji': '🔥',
        'tags': ['Bestseller', 'Fan Favorite']
    },
    'chocolate': {
        'name': 'Chocolate Cookie',
        'price': 65,
        'desc': 'A classic chocolate cookie baked to perfection with a soft, chewy center.',
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
            'SELECT * FROM orders WHERE customer_id = %s ORDER BY created_at DESC LIMIT 10',
            (session['user_id'],)
        )
        orders = cursor.fetchall()
        for order in orders:
            if 'created_at' in order and isinstance(order['created_at'], datetime):
                order['created_at'] = order['created_at'].strftime('%Y-%m-%d %H:%M')
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
    
    flash(f'Order placed! {quantity}x {COOKIES[cookie_type]["name"]}', 'success')
    return redirect(url_for('shop'))

# ── ADDED REVISION: DELETE ORDER ROUTE ──
@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # We verify the customer_id so users can only delete their own orders
            cursor.execute(
                'DELETE FROM orders WHERE id = %s AND customer_id = %s', 
                (order_id, session['user_id'])
            )
        flash('Order has been cancelled.', 'success')
    except Exception as e:
        flash('An error occurred while trying to cancel the order.', 'error')
    finally:
        conn.close()
    
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
                c['created_at'] = c['created_at'].strftime('%Y-%m-%d %H:%M')

        # Recent Transactions
        cursor.execute('''
            SELECT o.*, c.name, c.contact, c.address, c.email 
            FROM orders o JOIN customers c ON o.customer_id = c.id 
            ORDER BY o.created_at DESC LIMIT 30
        ''')
        recent_orders = cursor.fetchall()
        for ro in recent_orders:
            if isinstance(ro['created_at'], datetime):
                ro['created_at'] = ro['created_at'].strftime('%Y-%m-%d %H:%M')

        # Basic Counters calculations
        cursor.execute("SELECT SUM(total_price) as total_rev FROM orders WHERE status != 'Cancelled'")
        rev_row = cursor.fetchone()
        total_revenue = float(rev_row['total_rev']) if rev_row and rev_row['total_rev'] else 0.0

        cursor.execute("SELECT SUM(quantity) as total_qty FROM orders WHERE status != 'Cancelled'")
        qty_row = cursor.fetchone()
        total_cookies_sold = int(qty_row['total_qty']) if qty_row and qty_row['total_qty'] else 0

        cursor.execute('''
            SELECT cookie_type, SUM(quantity) as volume 
            FROM orders WHERE status != 'Cancelled' 
            GROUP BY cookie_type 
            ORDER BY volume DESC LIMIT 1
        ''')
        best_seller_row = cursor.fetchone()
        
        if best_seller_row:
            c_key = best_seller_row['cookie_type']
            best_cookie_name = COOKIES[c_key]['name'] if c_key in COOKIES else c_key
            best_cookie_sales = best_seller_row['volume']
        else:
            best_cookie_name = "No sales recorded"
            best_cookie_sales = 0

        # GRAPH DATA 1: Product Volume Sales (For Pie Chart)
        prod_labels = []
        prod_data = []
        for key, details in COOKIES.items():
            cursor.execute("SELECT SUM(quantity) as vol FROM orders WHERE cookie_type = %s AND status != 'Cancelled'", (key,))
            res = cursor.fetchone()
            val = int(res['vol']) if res and res['vol'] is not None else 0
            prod_labels.append(details['name'])
            prod_data.append(val)

        # GRAPH DATA 2: Chronological 7-Day Timeline Sales (For Line Chart)
        timeline_labels = []
        timeline_data = []
        for i in range(6, -1, -1):
            day_start = (datetime.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            cursor.execute("SELECT SUM(quantity) as qty FROM orders WHERE created_at >= %s AND created_at < %s AND status != 'Cancelled'", (day_start, day_end))
            row = cursor.fetchone()
            qty_val = int(row['qty']) if row and row['qty'] is not None else 0
            
            timeline_labels.append(day_start.strftime('%b %d'))
            timeline_data.append(qty_val)

        # Weekly listing arrays
        week_ago = (datetime.now() - timedelta(days=7))
        cursor.execute(
            "SELECT cookie_type, SUM(quantity) as total_qty, SUM(total_price) as total_rev FROM orders WHERE created_at >= %s GROUP BY cookie_type",
            (week_ago,)
        )
        weekly = cursor.fetchall()

    conn.close()
    return render_template('admin_dashboard.html',
                           customers=customers,
                           weekly=weekly,
                           recent_orders=recent_orders,
                           cookies=COOKIES,
                           total_revenue=total_revenue,
                           total_cookies_sold=total_cookies_sold,
                           best_cookie_name=best_cookie_name,
                           best_cookie_sales=best_cookie_sales,
                           chart_labels=json.dumps(prod_labels),
                           chart_data=json.dumps(prod_data),
                           time_labels=json.dumps(timeline_labels),
                           time_data=json.dumps(timeline_data))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    new_status = request.form.get('status')
    delivery_date = request.form.get('delivery_date', '').strip()
    if not delivery_date:
        delivery_date = "Not Scheduled Yet"

    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE orders SET status = %s, delivery_date = %s WHERE id = %s', (new_status, delivery_date, order_id))
    conn.close()
    flash(f'Order #{order_id} updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
