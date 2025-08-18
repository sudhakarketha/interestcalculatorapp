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
        # Check if we're in production (Render or Clever Cloud)
        is_production = 'RENDER' in os.environ or 'CC_PYTHON' in os.environ
        
        # First try MySQL connection
        cfg = _read_mysql_config_from_env()
        print(f"Attempting database connection with config: host={cfg['host']}, user={cfg['user']}, database={cfg['database']}, port={cfg['port']}")
        try:
            # Use a different connection approach for production vs development
            if is_production:
                # In production, use a more robust connection configuration
                connection = mysql.connector.connect(
                    host=cfg['host'],
                    user=cfg['user'],
                    password=cfg['password'],
                    database=cfg['database'],
                    port=int(cfg['port']),
                    # Critical production settings
                    use_pure=True,  # Use pure Python implementation for better compatibility
                    connection_timeout=60,  # Longer timeout for production
                    autocommit=False,  # We'll handle transactions explicitly
                    # Reconnection settings
                    get_warnings=True,
                    raise_on_warnings=True,
                    # Connection pool settings
                    pool_name="app_pool",
                    pool_size=5,
                    pool_reset_session=True
                )
            else:
                # Development connection with simpler settings
                connection = mysql.connector.connect(
                    host=cfg['host'],
                    user=cfg['user'],
                    password=cfg['password'],
                    database=cfg['database'],
                    port=int(cfg['port']),
                    autocommit=False
                )
            print("MySQL database connection successful")
            return connection
        except Exception as mysql_error:
            print(f"MySQL database connection error: {mysql_error}")
            
            # Allow fallback to SQLite in both development and production
            # This ensures the application can run even if MySQL is not available
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
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection for table creation")
            return
            
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        print(f"Creating tables using {'SQLite' if is_sqlite else 'MySQL'} syntax")
        
        cursor = connection.cursor()
        
        try:
            # Create investments table with syntax compatible with both SQLite and MySQL
            if is_sqlite:
                # First check if the table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='investments'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    print("Creating investments table in SQLite")
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
                            user_id INTEGER NOT NULL
                        )
                    ''')
                    print("SQLite investments table created successfully")
                else:
                    print("SQLite investments table already exists")
                    # Check if user_id column exists
                    cursor.execute("PRAGMA table_info(investments)")
                    columns = cursor.fetchall()
                    user_id_column = next((col for col in columns if col[1] == 'user_id'), None)
                    
                    if not user_id_column:
                        # Add user_id column if it doesn't exist
                        print("Adding missing user_id column to SQLite investments table")
                        cursor.execute("ALTER TABLE investments ADD COLUMN user_id INTEGER")
                        # Set a default value for existing records
                        cursor.execute("UPDATE investments SET user_id = 1 WHERE user_id IS NULL")
                        print("Added user_id column to SQLite investments table")
                    
                    # Check if user_id column is NOT NULL
                    cursor.execute("PRAGMA table_info(investments)")
                    columns = cursor.fetchall()
                    user_id_column = next((col for col in columns if col[1] == 'user_id'), None)
                    
                    if user_id_column and user_id_column[3] == 0:  # 3 is the index for NOT NULL constraint (0=nullable, 1=not null)
                        print("Updating user_id column to NOT NULL in SQLite investments table")
                        # SQLite doesn't support ALTER COLUMN directly, so we need to recreate the table
                        cursor.execute("ALTER TABLE investments RENAME TO investments_old")
                        cursor.execute('''
                            CREATE TABLE investments (
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
                                user_id INTEGER NOT NULL
                            )
                        ''')
                        cursor.execute("INSERT INTO investments SELECT * FROM investments_old WHERE user_id IS NOT NULL")
                        cursor.execute("DROP TABLE investments_old")
                        print("SQLite investments table updated with NOT NULL constraint on user_id")
                
                # Check if users table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    print("Creating users table in SQLite")
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL UNIQUE,
                            email TEXT NOT NULL UNIQUE,
                            password_hash TEXT NOT NULL,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    print("SQLite users table created successfully")
                else:
                    print("SQLite users table already exists")
            else:
                # MySQL syntax
                # Check if investments table exists
                cursor.execute("SHOW TABLES LIKE 'investments'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    print("Creating investments table in MySQL")
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
                            user_id INT NOT NULL
                        )
                    ''')
                    print("MySQL investments table created successfully")
                else:
                    print("MySQL investments table already exists")
                    # Check if user_id column exists
                    try:
                        cursor.execute("SELECT user_id FROM investments LIMIT 1")
                        cursor.fetchone()  # Just to check if the column exists
                        print("MySQL investments table has user_id column")
                    except Exception as column_error:
                        if "Unknown column 'user_id'" in str(column_error):
                            print("Adding missing user_id column to MySQL investments table")
                            cursor.execute("ALTER TABLE investments ADD COLUMN user_id INT")
                            # Set a default value for existing records
                            cursor.execute("UPDATE investments SET user_id = 1 WHERE user_id IS NULL")
                            print("Added user_id column to MySQL investments table")
                    
                    # Check if user_id column is NOT NULL
                    cursor.execute("DESCRIBE investments")
                    columns = cursor.fetchall()
                    for col in columns:
                        if col[0] == 'user_id' and 'YES' in str(col[2]):  # 'YES' in the Null field means it's nullable
                            print("Updating user_id column to NOT NULL in MySQL investments table")
                            cursor.execute("ALTER TABLE investments MODIFY user_id INT NOT NULL")
                            print("MySQL investments table updated with NOT NULL constraint on user_id")
                            break
                
                # Check if users table exists
                cursor.execute("SHOW TABLES LIKE 'users'")
                table_exists = cursor.fetchone()
                
                if not table_exists:
                    print("Creating users table in MySQL")
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(100) NOT NULL UNIQUE,
                            email VARCHAR(100) NOT NULL UNIQUE,
                            password_hash VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    print("MySQL users table created successfully")
                else:
                    print("MySQL users table already exists")
            
            # Explicitly commit changes
            connection.commit()
            print("Database tables created or verified successfully")
            
        except Exception as table_error:
            print(f"Error creating or updating tables: {table_error}")
            if connection:
                try:
                    connection.rollback()
                    print("Transaction rolled back due to error")
                except Exception as rollback_error:
                    print(f"Error during rollback: {rollback_error}")
            raise table_error
            
    except Exception as e:
        print(f"Critical error in create_table: {e}")
        # Log the error but continue - we want the app to try to run
        print(f"WARNING: Table creation error, but continuing: {e}")
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed after table creation")
            except Exception as e:
                print(f"Error closing connection: {e}")

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
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
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
        
        return jsonify({
            'message': 'Registration successful',
            'user': {'id': user_id, 'username': username, 'email': email}
        })
    
    except Exception as e:
        print(f"Error during registration: {e}")
        # Rollback transaction if there was an error
        if connection:
            try:
                connection.rollback()
                print("Transaction rolled back due to error")
            except Exception as rollback_error:
                print(f"Error during rollback: {rollback_error}")
        return jsonify({'error': 'Registration failed'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")


@app.route('/api/login', methods=['POST'])
def login():
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Validate input
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        print(f"Login attempt: username={username}")
        
        # Find user
        if is_sqlite:
            cursor = connection.cursor()
            cursor.execute('SELECT id, username, email, password_hash FROM users WHERE username = ?', (username,))
            user_row = cursor.fetchone()
            
            if not user_row:
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
            print(f"Login failed: Invalid credentials for username={username}")
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True
        
        print(f"Login successful: username={username}, user_id={user['id']}")
        
        return jsonify({
            'message': 'Login successful',
            'user': {'id': user['id'], 'username': user['username'], 'email': user['email']}
        })
    
    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({'error': f'Login failed: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")

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
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        print(f"Fetching investments for user_id={session['user_id']}")
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
        
        print(f"Successfully fetched {len(investments)} investments for user_id={session['user_id']}")
        return jsonify(investments)
    
    except Exception as e:
        print(f"Error fetching investments: {e}")
        return jsonify({'error': f'Failed to fetch investments: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")

@app.route('/api/investments', methods=['POST'])
@login_required
def add_investment():
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        data = request.json
        cursor = connection.cursor()
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        # Log the data being inserted
        print(f"Adding investment: id={data['id']}, name={data['name']}, user_id={session['user_id']}")
        
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
        
        # Explicitly commit the transaction
        connection.commit()
        print(f"Investment added successfully: id={data['id']}")
        
        return jsonify({'message': 'Investment added successfully'})
    
    except Exception as e:
        # Log detailed error information
        print(f"Error adding investment: {e}")
        # Rollback transaction if there was an error
        if connection:
            try:
                connection.rollback()
                print("Transaction rolled back due to error")
            except Exception as rollback_error:
                print(f"Error during rollback: {rollback_error}")
        
        return jsonify({'error': f'Failed to add investment: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")

@app.route('/api/investments/<int:investment_id>', methods=['PUT'])
@login_required
def update_investment(investment_id):
    print(f"PUT /api/investments/{investment_id} - Starting update")
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            print(f"PUT /api/investments/{investment_id} - Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
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
        
        # Explicitly commit the transaction
        connection.commit()
        print(f"PUT /api/investments/{investment_id} - Update successful")
        return jsonify({'message': 'Investment updated successfully'})
    
    except Exception as e:
        print(f"PUT /api/investments/{investment_id} - Error updating investment: {e}")
        # Rollback transaction if there was an error
        if connection:
            try:
                connection.rollback()
                print(f"PUT /api/investments/{investment_id} - Transaction rolled back due to error")
            except Exception as rollback_error:
                print(f"PUT /api/investments/{investment_id} - Error during rollback: {rollback_error}")
        return jsonify({'error': f'Failed to update investment: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"PUT /api/investments/{investment_id} - Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print(f"PUT /api/investments/{investment_id} - Database connection closed")
            except Exception as e:
                print(f"PUT /api/investments/{investment_id} - Error closing connection: {e}")

@app.route('/api/investments/<int:investment_id>', methods=['DELETE'])
@login_required
def delete_investment(investment_id):
    print(f"DELETE /api/investments/{investment_id} - Starting delete")
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            print(f"DELETE /api/investments/{investment_id} - Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
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
        
        # Explicitly commit the transaction
        connection.commit()
        print(f"DELETE /api/investments/{investment_id} - Delete successful")
        return jsonify({'message': 'Investment deleted successfully'})
    
    except Exception as e:
        print(f"DELETE /api/investments/{investment_id} - Error deleting investment: {e}")
        # Rollback transaction if there was an error
        if connection:
            try:
                connection.rollback()
                print(f"DELETE /api/investments/{investment_id} - Transaction rolled back due to error")
            except Exception as rollback_error:
                print(f"DELETE /api/investments/{investment_id} - Error during rollback: {rollback_error}")
        return jsonify({'error': f'Failed to delete investment: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"DELETE /api/investments/{investment_id} - Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print(f"DELETE /api/investments/{investment_id} - Database connection closed")
            except Exception as e:
                print(f"DELETE /api/investments/{investment_id} - Error closing connection: {e}")

@app.route('/api/investments', methods=['DELETE'])
@login_required
def clear_investments():
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        # Check if we're using SQLite or MySQL
        is_sqlite = hasattr(connection, 'row_factory')
        
        print(f"Clearing all investments for user_id={session['user_id']}")
        cursor = connection.cursor()
        if is_sqlite:
            cursor.execute('DELETE FROM investments WHERE user_id = ?', (session['user_id'],))
        else:
            cursor.execute('DELETE FROM investments WHERE user_id = %s', (session['user_id'],))
        
        # Explicitly commit the transaction
        connection.commit()
        print(f"All investments cleared successfully for user_id={session['user_id']}")
        return jsonify({'message': 'All investments cleared successfully'})
    
    except Exception as e:
        print(f"Error clearing investments: {e}")
        # Rollback transaction if there was an error
        if connection:
            try:
                connection.rollback()
                print("Transaction rolled back due to error")
            except Exception as rollback_error:
                print(f"Error during rollback: {rollback_error}")
        return jsonify({'error': f'Failed to clear investments: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")

@app.route('/api/export', methods=['GET'])
@login_required
def export_csv():
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        print(f"Exporting CSV data for user_id={session['user_id']}")
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
        
        print(f"Successfully exported {len(investments)} investments to CSV for user_id={session['user_id']}")
        return jsonify({'csv_data': '\n'.join(csv_data)})
    
    except Exception as e:
        print(f"Error exporting data: {e}")
        return jsonify({'error': f'Failed to export data: {str(e)}'}), 500
    
    finally:
        # Always close cursor and connection in finally block
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
        
        if connection:
            try:
                connection.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")

if __name__ == '__main__':
    create_table()
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
