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
        # Customers Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            contact VARCHAR(100) NOT NULL,
            address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Products Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'Available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Orders Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            cookie_type VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Comments/Feedback Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute("SHOW COLUMNS FROM orders LIKE 'delivery_date'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_date VARCHAR(100) DEFAULT 'Not Scheduled Yet'")
    conn.close()

try:
    init_db()
except Exception as e:
    print("Database init warning:", e)

COOKIES = {
    'smores': {
        'name': "S'mores",
        'price': 35,
        'desc': "Milk chocolate chip, graham crackers, and melted marshmallows.",
        'emoji': '🍪',
        'tags': ['Bestseller', 'Fan Favorite'],
        'status': 'Available'
    },
    'chocolate': {
        'name': 'Chocolate Chip Cookie',
        'price': 30,
        'desc': 'A classic chocolate cookie baked to perfection with a soft, chewy center.',
        'emoji': '🍫',
        'tags': ['Classic', 'All-Time Fave'],
        'status': 'Available'
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
        
    cookie_type = request.form.get('cookie_type')
    try:
        quantity = int(request.form.get('quantity', 0))
    except ValueError:
        quantity = 0
    
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

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders WHERE id = %s AND customer_id = %s', (order_id, session['user_id']))
    conn.close()
    flash('Order cancelled.', 'success')
    return redirect(url_for('shop'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    message = request.form.get('message', '').strip()
    if message:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO comments (customer_name, message) VALUES (%s, %s)',
                (session['user_name'], message)
            )
        conn.close()
        flash('Thank you for your sweet feedback!', 'success')
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
        # Fetch Products Table
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
        db_products = cursor.fetchall()

        # Customers Mapping
        cursor.execute('''
            SELECT c.id, c.name, c.email, c.contact, c.address, c.created_at, COUNT(o.id) as order_count 
            FROM customers c LEFT JOIN orders o ON c.id = o.customer_id 
            GROUP BY c.id, c.name, c.email, c.contact, c.address, c.created_at 
            ORDER BY c.created_at DESC
        ''')
        customers = cursor.fetchall()

        # Recent Transactions
        cursor.execute('''
            SELECT o.*, c.name, c.contact, c.address, c.email 
            FROM orders o JOIN customers c ON o.customer_id = c.id 
            ORDER BY o.created_at DESC LIMIT 30
        ''')
        recent_orders = cursor.fetchall()

        # Fetch Feedback/Comments (Renamed to match dashboard template)
        cursor.execute('SELECT id, customer_name AS user_name, message AS text FROM comments ORDER BY created_at DESC')
        customer_comments = cursor.fetchall()

        # Revenue & Sales Logic (Filter by Delivered orders if present, otherwise all non-cancelled)
        cursor.execute("SELECT SUM(total_price) as total_rev FROM orders WHERE status = 'Delivered'")
        rev_row = cursor.fetchone()
        total_revenue = float(rev_row['total_rev']) if rev_row and rev_row['total_rev'] else 0.0

        cursor.execute("SELECT SUM(quantity) as total_qty FROM orders WHERE status = 'Delivered'")
        qty_row = cursor.fetchone()
        total_cookies_sold = int(qty_row['total_qty']) if qty_row and qty_row['total_qty'] else 0

        # Graph Formatting (Real Data for Pie Chart)
        prod_labels, prod_data = [], []
        product_performance = []
        for key, details in COOKIES.items():
            cursor.execute("SELECT SUM(quantity) as vol, SUM(total_price) as sales FROM orders WHERE cookie_type = %s AND status = 'Delivered'", (key,))
            res = cursor.fetchone()
            vol = int(res['vol']) if res and res['vol'] else 0
            sales = float(res['sales']) if res and res['sales'] else 0.0
            prod_labels.append(details['name'])
            prod_data.append(vol)
            pct = (vol / total_cookies_sold * 100) if total_cookies_sold > 0 else 0.0
            product_performance.append({
                'name': details['name'],
                'quantity_sold': vol,
                'total_sales': sales,
                'percentage': pct
            })

        # Timeline Logic (Real Data for Line Chart)
        time_labels, time_data = [], []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).date()
            cursor.execute("SELECT SUM(quantity) as qty FROM orders WHERE DATE(created_at) = %s AND status = 'Delivered'", (day,))
            row = cursor.fetchone()
            time_labels.append(day.strftime('%b %d'))
            time_data.append(int(row['qty']) if row and row['qty'] else 0)

        # Identify Top Seller Name
        cursor.execute("SELECT cookie_type, SUM(quantity) as total FROM orders WHERE status = 'Delivered' GROUP BY cookie_type ORDER BY total DESC LIMIT 1")
        top_row = cursor.fetchone()
        best_cookie = top_row['cookie_type'] if top_row else "None"

    conn.close()
    return render_template('admin_dashboard.html',
                           products=db_products,
                           customers=customers,
                           recent_orders=recent_orders,
                           customer_comments=customer_comments,
                           cookies=COOKIES,
                           total_revenue=total_revenue,
                           total_cookies_sold=total_cookies_sold,
                           best_cookie_name=best_cookie.capitalize(),
                           product_performance=product_performance,
                           chart_labels=json.dumps(prod_labels),
                           chart_data=json.dumps(prod_data),
                           time_labels=json.dumps(time_labels),
                           time_data=json.dumps(time_data))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    name = request.form.get('name')
    price = request.form.get('price', 0)
    status = request.form.get('status', 'Available')
    description = request.form.get('description', '')

    if name and price:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO products (name, price, description, status) VALUES (%s, %s, %s, %s)',
                (name, float(price), description, status)
            )
        conn.close()
        flash(f'Product {name} added!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
    conn.close()
    flash('Product removed.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders WHERE customer_id = %s', (customer_id,))
        cursor.execute('DELETE FROM customers WHERE id = %s', (customer_id,))
    conn.close()
    flash('Customer removed.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_order/<int:order_id>', methods=['POST'])
def admin_delete_order(order_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders WHERE id = %s', (order_id,))
    conn.close()
    flash(f'Order #{order_id} deleted permanently.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
    conn.close()
    flash('Comment removed from portal.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    new_status = request.form.get('status')
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (new_status, order_id))
    conn.close()
    flash(f'Order #{order_id} updated.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
