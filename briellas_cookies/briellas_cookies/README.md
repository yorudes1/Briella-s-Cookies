# 🍪 Briella's Cookies — Website Setup Guide

## Requirements
- Python 3.8 or higher
- pip (Python package manager)

---

## How to Run (VS Code)

### 1. Open the project folder in VS Code
Open VS Code → File → Open Folder → select `briellas_cookies`

### 2. Open a Terminal in VS Code
Terminal → New Terminal  (or press Ctrl + `)

### 3. Install required packages
```
pip install -r requirements.txt
```

### 4. Run the app
```
python app.py
```

### 5. Open your browser and go to:
```
http://127.0.0.1:5000
```

---

## Pages & URLs

| URL | Page |
|-----|------|
| `/` | Redirects to Login |
| `/login` | Customer Login |
| `/register` | Customer Sign Up |
| `/shop` | Cookie Menu & Order |
| `/admin` | Admin Login |
| `/admin/dashboard` | Admin Dashboard |

---

## Admin Credentials
- **Username:** `AdminBriella`
- **Password:** `12345`

---

## Business Info
- **Name:** Briella's Cookies
- **Contact:** 0906 512 5377
- **Facebook:** Lara Cinco

---

## Cookie Menu

| Cookie | Price |
|--------|-------|
| S'mores Cookie | ₱75/pc |
| Chocolate Cookie | ₱65/pc |

---

## Project Structure
```
briellas_cookies/
├── app.py              ← Main Flask application
├── requirements.txt    ← Python dependencies
├── briellas.db         ← SQLite database (auto-created on first run)
└── templates/
    ├── base.html           ← Shared layout & styles
    ├── login.html          ← Customer login page
    ├── register.html       ← Customer registration
    ├── shop.html           ← Cookie menu & ordering
    ├── admin_login.html    ← Admin login page
    └── admin_dashboard.html← Admin dashboard with charts
```
