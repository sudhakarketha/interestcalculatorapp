from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
import os
from datetime import datetime, timedelta
import json
from urllib.parse import urlparse
import bcrypt
import secrets
from functools import wraps

# Import configuration for local testing
try:
    import config
except ImportError:
    pass

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configure session
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Authentication middleware
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Database configuration (supports DATABASE_URL or MYSQL_* vars)
def _read_mysql_config_from_env():
    """Return a dict with MySQL connection params from env vars.

    Priority:
    1) DATABASE_URL (e.g. mysql://user:pass@host:3306/db)
    2) MYSQL_ADDON_* variables (Clever Cloud style)
    3) Local defaults
    """
    database_url = os.environ.get('DATABASE_URL')
    print(f"DATABASE_URL from env: {database_url}")
    
    if database_url:
        try:
            parsed = urlparse(database_url)
            print(f"Parsed DATABASE_URL: hostname={parsed.hostname}, username={parsed.username}, path={parsed.path}, port={parsed.port}")
            # Some providers prefix with mysql://
            config = {
                'host': parsed.hostname or 'localhost',
                'user': parsed.username or 'root',
                'password': parsed.password or '',
                'database': (parsed.path[1:] if parsed.path and len(parsed.path) > 1 else ''),
                'port': int(parsed.port or 3306),
            }
            print(f"Using DATABASE_URL config: {config}")
            return config
        except Exception as parse_error:
            print(f"Failed to parse DATABASE_URL: {parse_error}")
    
    # Fallback to individual env vars
    config = {
        'host': os.environ.get('MYSQL_ADDON_HOST', 'localhost'),
        'user': os.environ.get('MYSQL_ADDON_USER', 'root'),
        'password': os.environ.get('MYSQL_ADDON_PASSWORD', ''),
        'database': os.environ.get('MYSQL_ADDON_DB', 'interest_calculator'),
        'port': int(os.environ.get('MYSQL_ADDON_PORT', 3306)),
    }
    print(f"Using fallback config: {config}")
    return config


def get_db_connection():
    try:
        # First try MySQL connection
        cfg = _read_mysql_config_from_env()
        print(f"Attempting database connection with config: host={cfg['host']}, user={cfg['user']}, database={cfg['database']}, port={cfg['port']}")
        try:
            connection = mysql.connector.connect(
                host=cfg['host'],
                user=cfg['user'],
                password=cfg['password'],
                database=cfg['database'],
                port=int(cfg['port'])
            )
            print("MySQL database connection successful")
            return connection
        except Exception as mysql_error:
            print(f"MySQL database connection error: {mysql_error}")
            # Fallback to SQLite for local development
            import sqlite3
            print("Falling back to SQLite database")
            sqlite_connection = sqlite3.connect('test_interest_calculator.db')
            sqlite_connection.row_factory = sqlite3.Row
            print("SQLite database connection successful")
            return sqlite_connection
    except Exception as e:
        print(f"All database connection attempts failed: {e}")
        return None

# Create database tables
def create_table():
    connection = get_db_connection()
    if connection:
        try:
            # Check if we're using SQLite or MySQL
            is_sqlite = hasattr(connection, 'row_factory')
            
            cursor = connection.cursor()
            
            # Create investments table with syntax compatible with both SQLite and MySQL
            if is_sqlite:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS investments (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        principal REAL NOT NULL,
                        rate REAL NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT,
                        months REAL DEFAULT 0,
                        simple_interest REAL DEFAULT 0,
                        compound_interest REAL DEFAULT 0,
                        total_simple REAL DEFAULT 0,
                        total_compound REAL DEFAULT 0,
                        calculation_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER
                    )
                ''')
                
                # Create users table for SQLite
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                # MySQL syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS investments (
                        id BIGINT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        principal DECIMAL(15,2) NOT NULL,
                        rate DECIMAL(5,2) NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE,
                        months DECIMAL(8,2) DEFAULT 0,
                        simple_interest DECIMAL(15,2) DEFAULT 0,
                        compound_interest DECIMAL(15,2) DEFAULT 0,
                        total_simple DECIMAL(15,2) DEFAULT 0,
                        total_compound DECIMAL(15,2) DEFAULT 0,
                        calculation_date DATETIME,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_id INT
                    )
                ''')
                
                # Create users table for MySQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(100) NOT NULL UNIQUE,
                        email VARCHAR(100) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            
            connection.commit()
            cursor.close()
            connection.close()
            print("Database table created successfully")
        except Exception as e:
            print(f"Error creating table: {e}")
    else:
        print("Skipping table creation because database connection was not established")

# Ensure the table exists when the module is imported (works under Gunicorn on Render)
create_table()

# Helper to parse various datetime string formats into MySQL DATETIME
def parse_calculation_datetime(raw_value: str):
    if not raw_value:
        return None
    try:
        # Handle ISO strings with Zulu or offset
        value = str(raw_value)
        if value.endswith('Z'):
            value = value.replace('Z', '+00:00')
        # fromisoformat handles "YYYY-MM-DDTHH:MM:SS[.ffffff][+HH:MM]"
        dt = datetime.fromisoformat(value)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    try:
        # Handle common locale string, e.g., "12/8/2025, 12:29:58 pm"
        # Allow both lower/upper case AM/PM
        for fmt in (
            '%m/%d/%Y, %I:%M:%S %p',
            '%m/%d/%Y %I:%M:%S %p',
            '%d/%m/%Y, %I:%M:%S %p',
            '%d-%m-%Y %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
        ):
            try:
                dt = datetime.strptime(raw_value, fmt)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                continue
    except Exception:
        pass
    # Fallback: store NULL if unparsable
    return None

@app.route('/login')
def login_page():
    return app.send_static_file('login.html')

@app.route('/')
def index():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return app.send_static_file('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validate input
        if not username or not email or not password:
            return jsonify({'error': 'Username, email and password are required'}), 400
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        # Check if username or email already exists
        cursor = connection.cursor(dictionary=True) if not is_sqlite else connection.cursor()
        
        if is_sqlite:
            cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        else:
            cursor.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
            
        existing_user = cursor.fetchone()
        
        if existing_user:
            return jsonify({'error': 'Username or email already exists'}), 409
        
        # Hash the password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert new user
        if is_sqlite:
            cursor.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, password_hash.decode('utf-8'))
            )
        else:
            cursor.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                (username, email, password_hash.decode('utf-8'))
            )
        connection.commit()
        
        # Get the new user ID
        user_id = cursor.lastrowid
        
        # Set session
        session['user_id'] = user_id
        session['username'] = username
        session.permanent = True
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'Registration successful',
            'user': {'id': user_id, 'username': username, 'email': email}
        })
    
    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Validate input
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        # Find user
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('SELECT id, username, email, password_hash FROM users WHERE username = ?', (username,))
            user_row = cursor.fetchone()
            
            if not user_row:
                cursor.close()
                connection.close()
                return jsonify({'error': 'Invalid username or password'}), 401
                
            # Convert SQLite row to dict
            user = {
                'id': user_row[0],
                'username': user_row[1],
                'email': user_row[2],
                'password_hash': user_row[3]
            }
        else:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT id, username, email, password_hash FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'Login successful',
            'user': {'id': user['id'], 'username': user['username'], 'email': user['email']}
        })
    
    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'})

@app.route('/api/user', methods=['GET'])
@login_required
def get_current_user():
    user_id = session.get('user_id')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    # Check if we're using SQLite or MySQL
    is_sqlite = hasattr(connection, 'row_factory')
    
    if is_sqlite:
        cursor = connection.cursor()
        cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            cursor.close()
            connection.close()
            return jsonify({'error': 'User not found'}), 404
            
        # Convert SQLite row to dict
        user = {
            'id': user_row[0],
            'username': user_row[1],
            'email': user_row[2]
        }
    else:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': {'id': user['id'], 'username': user['username'], 'email': user['email']}
    })

@app.route('/api/investments', methods=['GET'])
@login_required
def get_investments():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('''
                SELECT * FROM investments 
                WHERE user_id = ?
                ORDER BY created_at DESC 
                LIMIT 50
            ''', (session['user_id'],))
            
            # Convert SQLite rows to dict
            column_names = [description[0] for description in cursor.description]
            investments = []
            for row in cursor.fetchall():
                investment = {}
                for i, value in enumerate(row):
                    investment[column_names[i]] = value
                investments.append(investment)
        else:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM investments 
                WHERE user_id = %s
                ORDER BY created_at DESC 
                LIMIT 50
            ''', (session['user_id'],))
            investments = cursor.fetchall()
        
        # Convert dates to strings for JSON serialization
        for inv in investments:
            if inv['start_date']:
                inv['start_date'] = inv['start_date'] if isinstance(inv['start_date'], str) else inv['start_date'].isoformat()
            if inv['end_date']:
                inv['end_date'] = inv['end_date'] if isinstance(inv['end_date'], str) else inv['end_date'].isoformat()
            if inv['calculation_date']:
                inv['calculation_date'] = inv['calculation_date'] if isinstance(inv['calculation_date'], str) else inv['calculation_date'].isoformat()
            if inv['created_at']:
                inv['created_at'] = inv['created_at'] if isinstance(inv['created_at'], str) else inv['created_at'].isoformat()
        
        cursor.close()
        connection.close()
        return jsonify(investments)
    
    except Exception as e:
        print(f"Error fetching investments: {e}")
        return jsonify({'error': 'Failed to fetch investments'}), 500

@app.route('/api/investments', methods=['POST'])
@login_required
def add_investment():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
        cursor = connection.cursor()
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        if is_sqlite:
            cursor.execute('''
                INSERT INTO investments 
                (id, name, principal, rate, start_date, end_date, months, 
                 simple_interest, compound_interest, total_simple, total_compound, calculation_date, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['id'],
                data['name'],
                data['principal'],
                data['rate'],
                data['startDate'],
                data.get('endDate') or None,
                data.get('months', 0),
                data.get('simpleInterest', 0),
                data.get('compoundInterest', 0),
                data.get('totalSimple', data['principal']),
                data.get('totalCompound', data['principal']),
                parse_calculation_datetime(data.get('calculationDate')),
                session['user_id']
            ))
        else:
            cursor.execute('''
                INSERT INTO investments 
                (id, name, principal, rate, start_date, end_date, months, 
                 simple_interest, compound_interest, total_simple, total_compound, calculation_date, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                data['id'],
                data['name'],
                data['principal'],
                data['rate'],
                data['startDate'],
                data.get('endDate') or None,
                data.get('months', 0),
                data.get('simpleInterest', 0),
                data.get('compoundInterest', 0),
                data.get('totalSimple', data['principal']),
                data.get('totalCompound', data['principal']),
                parse_calculation_datetime(data.get('calculationDate')),
                session['user_id']
            ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Investment added successfully'})
    
    except Exception as e:
        print(f"Error adding investment: {e}")
        return jsonify({'error': 'Failed to add investment'}), 500

@app.route('/api/investments/<int:investment_id>', methods=['PUT'])
@login_required
def update_investment(investment_id):
    print(f"PUT /api/investments/{investment_id} - Starting update")
    connection = get_db_connection()
    if not connection:
        print(f"PUT /api/investments/{investment_id} - Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        # Check if investment belongs to the logged-in user
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('SELECT id FROM investments WHERE id = ? AND user_id = ?', 
                          (investment_id, session['user_id']))
            investment = cursor.fetchone()
        else:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT id FROM investments WHERE id = %s AND user_id = %s', 
                          (investment_id, session['user_id']))
            investment = cursor.fetchone()
        
        if not investment:
            return jsonify({'error': 'Investment not found or access denied'}), 404
        
        data = request.json
        print(f"PUT /api/investments/{investment_id} - Request data: {data}")
        cursor = connection.cursor()
        
        if is_sqlite:
            cursor.execute('''
                UPDATE investments 
                SET end_date = ?, months = ?, simple_interest = ?, 
                    compound_interest = ?, total_simple = ?, total_compound = ?, 
                    calculation_date = ?
                WHERE id = ? AND user_id = ?
            ''', (
                data['endDate'],
                data['months'],
                data['simpleInterest'],
                data['compoundInterest'],
                data['totalSimple'],
                data['totalCompound'],
                parse_calculation_datetime(data.get('calculationDate')),
                investment_id,
                session['user_id']
            ))
        else:
            cursor.execute('''
                UPDATE investments 
                SET end_date = %s, months = %s, simple_interest = %s, 
                    compound_interest = %s, total_simple = %s, total_compound = %s, 
                    calculation_date = %s
                WHERE id = %s AND user_id = %s
            ''', (
                data['endDate'],
                data['months'],
                data['simpleInterest'],
                data['compoundInterest'],
                data['totalSimple'],
                data['totalCompound'],
                parse_calculation_datetime(data.get('calculationDate')),
                investment_id,
                session['user_id']
            ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"PUT /api/investments/{investment_id} - Update successful")
        return jsonify({'message': 'Investment updated successfully'})
    
    except Exception as e:
        print(f"PUT /api/investments/{investment_id} - Error updating investment: {e}")
        return jsonify({'error': f'Failed to update investment: {str(e)}'}), 500

@app.route('/api/investments/<int:investment_id>', methods=['DELETE'])
@login_required
def delete_investment(investment_id):
    print(f"DELETE /api/investments/{investment_id} - Starting delete")
    connection = get_db_connection()
    if not connection:
        print(f"DELETE /api/investments/{investment_id} - Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        # Check if investment belongs to the logged-in user
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('SELECT id FROM investments WHERE id = ? AND user_id = ?', 
                          (investment_id, session['user_id']))
            investment = cursor.fetchone()
        else:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT id FROM investments WHERE id = %s AND user_id = %s', 
                          (investment_id, session['user_id']))
            investment = cursor.fetchone()
        
        if not investment:
            return jsonify({'error': 'Investment not found or access denied'}), 404
        
        cursor = connection.cursor()
        if is_sqlite:
            cursor.execute('DELETE FROM investments WHERE id = ? AND user_id = ?', 
                          (investment_id, session['user_id']))
        else:
            cursor.execute('DELETE FROM investments WHERE id = %s AND user_id = %s', 
                          (investment_id, session['user_id']))
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"DELETE /api/investments/{investment_id} - Delete successful")
        return jsonify({'message': 'Investment deleted successfully'})
    
    except Exception as e:
        print(f"DELETE /api/investments/{investment_id} - Error deleting investment: {e}")
        return jsonify({'error': f'Failed to delete investment: {str(e)}'}), 500

@app.route('/api/investments', methods=['DELETE'])
@login_required
def clear_investments():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        cursor = connection.cursor()
        if is_sqlite:
            cursor.execute('DELETE FROM investments WHERE user_id = ?', (session['user_id'],))
        else:
            cursor.execute('DELETE FROM investments WHERE user_id = %s', (session['user_id'],))
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'All investments cleared successfully'})
    
    except Exception as e:
        print(f"Error clearing investments: {e}")
        return jsonify({'error': 'Failed to clear investments'}), 500

@app.route('/api/export', methods=['GET'])
@login_required
def export_csv():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM investments WHERE user_id = ? ORDER BY created_at DESC', 
                          (session['user_id'],))
            rows = cursor.fetchall()
            
            # Convert SQLite rows to dict
            investments = []
            column_names = [description[0] for description in cursor.description]
            for row in rows:
                investment = {}
                for i, value in enumerate(row):
                    investment[column_names[i]] = value
                investments.append(investment)
        else:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT * FROM investments WHERE user_id = %s ORDER BY created_at DESC', 
                          (session['user_id'],))
            investments = cursor.fetchall()
        
        csv_data = []
        headers = ['Name', 'Principal', 'Rate (% per month)', 'Start Date', 'End Date', 
                  'Months', 'Simple Interest', 'Compound Interest', 'Total (Simple)', 
                  'Total (Compound)', 'Total Amount', 'Calculation Date']
        csv_data.append(','.join(headers))
        
        for inv in investments:
            # Calculate Total Amount (Principal + Simple Interest)
            total_amount = inv['principal'] + (inv['simple_interest'] or 0)
            
            row = [
                f'"{inv["name"]}"',
                 str(inv['principal']),
                 f'{inv["rate"]}%/month',
                 inv['start_date'] if isinstance(inv['start_date'], str) else inv['start_date'].isoformat() if inv['start_date'] else '',
                 inv['end_date'] if isinstance(inv['end_date'], str) else inv['end_date'].isoformat() if inv['end_date'] else '',
                 f'{inv["months"]:.2f}' if inv['months'] > 0 else '',
                 str(inv['simple_interest']) if inv['simple_interest'] > 0 else '',
                 str(inv['compound_interest']) if inv['compound_interest'] > 0 else '',
                 str(inv['total_simple']),
                 str(inv['total_compound']),
                 str(total_amount),
                 f'"{inv["calculation_date"]}"' if inv['calculation_date'] else ''
            ]
            csv_data.append(','.join(row))
        
        cursor.close()
        connection.close()
        
        return jsonify({'csv_data': '\n'.join(csv_data)})
    
    except Exception as e:
        print(f"Error exporting data: {e}")
        return jsonify({'error': 'Failed to export data'}), 500

if __name__ == '__main__':
    create_table()
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
