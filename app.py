from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import os
from datetime import datetime
import json
from urllib.parse import urlparse

# Import configuration for local testing
try:
    import config
except ImportError:
    pass

app = Flask(__name__)
CORS(app)

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
        cfg = _read_mysql_config_from_env()
        print(f"Attempting database connection with config: host={cfg['host']}, user={cfg['user']}, database={cfg['database']}, port={cfg['port']}")
        connection = mysql.connector.connect(
            host=cfg['host'],
            user=cfg['user'],
            password=cfg['password'],
            database=cfg['database'],
            port=int(cfg['port'])
        )
        print("Database connection successful")
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Create database table
def create_table():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
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

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/investments', methods=['GET'])
def get_investments():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT * FROM investments 
            ORDER BY created_at DESC 
            LIMIT 50
        ''')
        investments = cursor.fetchall()
        
        # Convert dates to strings for JSON serialization
        for inv in investments:
            if inv['start_date']:
                inv['start_date'] = inv['start_date'].isoformat()
            if inv['end_date']:
                inv['end_date'] = inv['end_date'].isoformat()
            if inv['calculation_date']:
                inv['calculation_date'] = inv['calculation_date'].isoformat()
            if inv['created_at']:
                inv['created_at'] = inv['created_at'].isoformat()
        
        cursor.close()
        connection.close()
        return jsonify(investments)
    
    except Exception as e:
        print(f"Error fetching investments: {e}")
        return jsonify({'error': 'Failed to fetch investments'}), 500

@app.route('/api/investments', methods=['POST'])
def add_investment():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
        cursor = connection.cursor()
        
        cursor.execute('''
            INSERT INTO investments 
            (id, name, principal, rate, start_date, end_date, months, 
             simple_interest, compound_interest, total_simple, total_compound, calculation_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            parse_calculation_datetime(data.get('calculationDate'))
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Investment added successfully'})
    
    except Exception as e:
        print(f"Error adding investment: {e}")
        return jsonify({'error': 'Failed to add investment'}), 500

@app.route('/api/investments/<int:investment_id>', methods=['PUT'])
def update_investment(investment_id):
    print(f"PUT /api/investments/{investment_id} - Starting update")
    connection = get_db_connection()
    if not connection:
        print(f"PUT /api/investments/{investment_id} - Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
        print(f"PUT /api/investments/{investment_id} - Request data: {data}")
        cursor = connection.cursor()
        
        cursor.execute('''
            UPDATE investments 
            SET end_date = %s, months = %s, simple_interest = %s, 
                compound_interest = %s, total_simple = %s, total_compound = %s, 
                calculation_date = %s
            WHERE id = %s
        ''', (
            data['endDate'],
            data['months'],
            data['simpleInterest'],
            data['compoundInterest'],
            data['totalSimple'],
            data['totalCompound'],
            parse_calculation_datetime(data.get('calculationDate')),
            investment_id
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
def delete_investment(investment_id):
    print(f"DELETE /api/investments/{investment_id} - Starting delete")
    connection = get_db_connection()
    if not connection:
        print(f"DELETE /api/investments/{investment_id} - Database connection failed")
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM investments WHERE id = %s', (investment_id,))
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"DELETE /api/investments/{investment_id} - Delete successful")
        return jsonify({'message': 'Investment deleted successfully'})
    
    except Exception as e:
        print(f"DELETE /api/investments/{investment_id} - Error deleting investment: {e}")
        return jsonify({'error': f'Failed to delete investment: {str(e)}'}), 500

@app.route('/api/investments', methods=['DELETE'])
def clear_investments():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM investments')
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'All investments cleared successfully'})
    
    except Exception as e:
        print(f"Error clearing investments: {e}")
        return jsonify({'error': 'Failed to clear investments'}), 500

@app.route('/api/export', methods=['GET'])
def export_csv():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM investments ORDER BY created_at DESC')
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
                inv['start_date'].isoformat() if inv['start_date'] else '',
                inv['end_date'].isoformat() if inv['end_date'] else '',
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
