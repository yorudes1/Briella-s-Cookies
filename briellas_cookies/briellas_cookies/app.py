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
            delivery_date VARCHAR(100) DEFAULT 'Not Scheduled Yet',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.close()

init_db()

COOKIES = {
    'smores': {'name': "S'mores Cookie", 'price': 75},
    'chocolate': {'name': 'Chocolate Cookie', 'price': 65}
}

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
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name, email = request.form['name'].strip(), request.form['email'].strip()
        hashed = generate_password_hash(request.form['password'])
        conn = get_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute('INSERT INTO customers (name, email, password, contact, address) VALUES (%s, %s, %s, %s, %s)',
                               (name, email, hashed, request.form['contact'], request.form['address']))
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email already registered.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/shop')
def shop():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM orders WHERE customer_id = %s ORDER BY created_at DESC', (session['user_id'],))
        orders = cursor.fetchall()
    conn.close()
    return render_template('shop.html', cookies=COOKIES, orders=orders)

@app.route('/order', methods=['POST'])
def order():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctype = request.form['cookie_type']
    qty = int(request.form.get('quantity', 1))
    price = COOKIES[ctype]['price'] * qty
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('INSERT INTO orders (customer_id, cookie_type, quantity, total_price) VALUES (%s, %s, %s, %s)',
                       (session['user_id'], COOKIES[ctype]['name'], qty, price))
    conn.close()
    flash('Order placed successfully!', 'success')
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
        flash('Thank you for your feedback!', 'success')
    return redirect(url_for('shop'))

# ── Admin Routes ─────────────────────────────────────────────────────────────

ADMIN_USER, ADMIN_PASS = 'AdminBriella', '12345'

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid Admin Credentials', 'error')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM customers ORDER BY created_at DESC')
        customers = cursor.fetchall()
        cursor.execute('SELECT o.*, c.name, c.contact FROM orders o JOIN customers c ON o.customer_id = c.id ORDER BY o.created_at DESC')
        recent_orders = cursor.fetchall()
        cursor.execute('SELECT * FROM comments ORDER BY created_at DESC')
        feedback = cursor.fetchall()
        
        # Calculate Stats
        cursor.execute("SELECT SUM(total_price) as rev, SUM(quantity) as qty FROM orders WHERE status != 'Cancelled'")
        stats_row = cursor.fetchone()
        total_revenue = float(stats_row['rev']) if stats_row['rev'] else 0.0
        total_cookies = int(stats_row['qty']) if stats_row['qty'] else 0

        # Chart Data: Flavor Volume
        prod_labels, prod_data = [], []
        for c_key, c_val in COOKIES.items():
            cursor.execute("SELECT SUM(quantity) as vol FROM orders WHERE cookie_type = %s AND status != 'Cancelled'", (c_val['name'],))
            res = cursor.fetchone()
            prod_labels.append(c_val['name'])
            prod_data.append(int(res['vol']) if res['vol'] else 0)

        # Chart Data: 7-Day Timeline
        time_labels, time_data = [], []
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).date()
            cursor.execute("SELECT SUM(quantity) as qty FROM orders WHERE DATE(created_at) = %s AND status != 'Cancelled'", (day,))
            row = cursor.fetchone()
            time_labels.append(day.strftime('%b %d'))
            time_data.append(int(row['qty']) if row['qty'] else 0)

    conn.close()
    
    # Check for top seller
    best_cookie = prod_labels[prod_data.index(max(prod_data))] if sum(prod_data) > 0 else "None"

    return render_template('admin_dashboard.html',
                           customers=customers, recent_orders=recent_orders, feedback=feedback,
                           total_revenue=total_revenue, total_cookies_sold=total_cookies,
                           best_cookie_name=best_cookie,
                           chart_labels=json.dumps(prod_labels), chart_data=json.dumps(prod_data),
                           time_labels=json.dumps(time_labels), time_data=json.dumps(time_data))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    status = request.form.get('status')
    d_date = request.form.get('delivery_date')
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE orders SET status = %s, delivery_date = %s WHERE id = %s', (status, d_date, order_id))
    conn.close()
    flash(f'Order #{order_id} updated.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_order/<int:order_id>', methods=['POST'])
def admin_delete_order(order_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM orders WHERE id = %s', (order_id,))
    conn.close()
    flash(f'Order #{order_id} permanently deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
    conn.close()
    flash('Comment deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
