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
        # 1. Customers Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            contact VARCHAR(100) NOT NULL,
            address TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # 2. Products Table (The new requirement for Admin Dashboard)
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            emoji VARCHAR(50),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )''')

        # 3. Orders Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            cookie_type VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'Pending',
            delivery_date VARCHAR(100) DEFAULT 'Not Scheduled Yet',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # 4. Comments Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.close()

# Initialize DB on start
try:
    init_db()
except Exception as e:
    print(f"Database Init Error: {e}")

# ── Customer Routes ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
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
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        contact = request.form.get('contact', '').strip()
        address = request.form.get('address', '').strip()
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
        except:
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
        cursor.execute('SELECT * FROM products WHERE is_active = 1')
        available_products = cursor.fetchall()
        cursor.execute('SELECT * FROM orders WHERE customer_id = %s ORDER BY created_at DESC', (session['user_id'],))
        orders = cursor.fetchall()
    conn.close()
    return render_template('shop.html', cookies=available_products, orders=orders)

@app.route('/order', methods=['POST'])
def order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    pid = request.form.get('product_id')
    qty = int(request.form.get('quantity', 1))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM products WHERE id = %s', (pid,))
        product = cursor.fetchone()
        if product:
            total = float(product['price']) * qty
            cursor.execute(
                'INSERT INTO orders (customer_id, cookie_type, quantity, total_price) VALUES (%s, %s, %s, %s)',
                (session['user_id'], product['name'], qty, total)
            )
            flash(f'Order placed for {product["name"]}!', 'success')
    conn.close()
    return redirect(url_for('shop'))

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders WHERE id = %s AND customer_id = %s', (order_id, session['user_id']))
    conn.close()
    flash('Order cancelled.', 'success')
    return redirect(url_for('shop'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_name' not in session: return redirect(url_for('login'))
    msg = request.form.get('message', '').strip()
    if msg:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO comments (customer_name, message) VALUES (%s, %s)', (session['user_name'], msg))
        conn.close()
        flash('Feedback sent!', 'success')
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
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM products')
        products = cursor.fetchall()
        cursor.execute('SELECT * FROM customers ORDER BY created_at DESC')
        customers = cursor.fetchall()
        cursor.execute('SELECT o.*, c.name, c.contact FROM orders o JOIN customers c ON o.customer_id = c.id ORDER BY o.created_at DESC')
        recent_orders = cursor.fetchall()
        cursor.execute('SELECT id, customer_name AS user_name, message AS text FROM comments ORDER BY created_at DESC')
        customer_comments = cursor.fetchall()

        cursor.execute("SELECT SUM(total_price) as rev FROM orders WHERE status != 'Cancelled'")
        total_rev = cursor.fetchone()['rev'] or 0
        cursor.execute("SELECT SUM(quantity) as qty FROM orders WHERE status != 'Cancelled'")
        total_sold = cursor.fetchone()['qty'] or 0
    conn.close()
    
    return render_template('admin_dashboard.html',
                           products=products, customers=customers, 
                           recent_orders=recent_orders, customer_comments=customer_comments,
                           total_revenue=total_rev, total_cookies_sold=total_sold,
                           chart_labels=json.dumps(["Orders"]), chart_data=json.dumps([int(total_sold)]),
                           time_labels=json.dumps(["Today"]), time_data=json.dumps([int(total_sold)]))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    name = request.form.get('name')
    price = request.form.get('price')
    emoji = request.form.get('emoji', '🍪')
    desc = request.form.get('desc', '')
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('INSERT INTO products (name, price, emoji, description) VALUES (%s, %s, %s, %s)', 
                       (name, price, emoji, desc))
    conn.close()
    flash('Product added!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_stock/<int:pid>', methods=['POST'])
def toggle_stock(pid):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE products SET is_active = NOT is_active WHERE id = %s', (pid,))
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    new_status = request.form.get('status')
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (new_status, order_id))
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
