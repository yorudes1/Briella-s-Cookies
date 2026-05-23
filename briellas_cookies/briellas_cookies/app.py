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
        
        # NEW: Products Table (Replaces the hardcoded COOKIES dict)
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            emoji VARCHAR(50),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE
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
    conn.close()

init_db()

# ── Customer Routes ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
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
        # Pull active products from DB
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
    
    product_id = request.form['product_id']
    quantity = int(request.form['quantity'])
    
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product = cursor.fetchone()
        if product:
            total = float(product['price']) * quantity
            cursor.execute(
                'INSERT INTO orders (customer_id, cookie_type, quantity, total_price) VALUES (%s, %s, %s, %s)',
                (session['user_id'], product['name'], quantity, total)
            )
            flash(f'Order placed! {quantity}x {product["name"]}', 'success')
    conn.close()
    return redirect(url_for('shop'))

# ── Admin Routes ─────────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db()
    with conn.cursor() as cursor:
        # 1. Fetch all products (for Tab 3)
        cursor.execute('SELECT * FROM products')
        all_products = cursor.fetchall()

        # 2. Fetch Customers
        cursor.execute('SELECT * FROM customers ORDER BY created_at DESC')
        customers = cursor.fetchall()

        # 3. Recent Orders
        cursor.execute('SELECT o.*, c.name, c.contact FROM orders o JOIN customers c ON o.customer_id = c.id ORDER BY o.created_at DESC')
        recent_orders = cursor.fetchall()

        # 4. Feedback
        cursor.execute('SELECT id, customer_name AS user_name, message AS text FROM comments ORDER BY created_at DESC')
        customer_comments = cursor.fetchall()

        # Stats logic
        cursor.execute("SELECT SUM(total_price) as rev FROM orders WHERE status != 'Cancelled'")
        total_revenue = cursor.fetchone()['rev'] or 0
        cursor.execute("SELECT SUM(quantity) as qty FROM orders WHERE status != 'Cancelled'")
        total_cookies_sold = cursor.fetchone()['qty'] or 0

        # Chart Data
        cursor.execute("SELECT cookie_type, SUM(quantity) as vol FROM orders GROUP BY cookie_type")
        chart_res = cursor.fetchall()
        chart_labels = [r['cookie_type'] for r in chart_res]
        chart_data = [int(r['vol']) for r in chart_res]

    conn.close()
    return render_template('admin_dashboard.html',
                           products=all_products,
                           customers=customers,
                           recent_orders=recent_orders,
                           customer_comments=customer_comments,
                           total_revenue=total_revenue,
                           total_cookies_sold=total_cookies_sold,
                           best_cookie_name="Stats Updated",
                           chart_labels=json.dumps(chart_labels),
                           chart_data=json.dumps(chart_data),
                           time_labels=json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
                           time_data=json.dumps([0,0,0,0,0,0,0]))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    name = request.form.get('name')
    price = request.form.get('price')
    emoji = request.form.get('emoji')
    desc = request.form.get('desc')
    
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('INSERT INTO products (name, price, emoji, description) VALUES (%s, %s, %s, %s)',
                       (name, price, emoji, desc))
    conn.close()
    flash(f'Product {name} added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_stock/<int:pid>', methods=['POST'])
def toggle_stock(pid):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE products SET is_active = NOT is_active WHERE id = %s', (pid,))
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<int:pid>', methods=['POST'])
def delete_product(pid):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM products WHERE id = %s', (pid,))
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
