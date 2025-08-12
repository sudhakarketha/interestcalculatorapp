from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import os
from datetime import datetime
import json

# Import configuration for local testing
try:
    import config
except ImportError:
    pass

app = Flask(__name__)
CORS(app)

# Database configuration for Clever Cloud
def get_db_connection():
    try:
        # Clever Cloud MySQL configuration
        connection = mysql.connector.connect(
            host=os.environ.get('MYSQL_ADDON_HOST', 'localhost'),
            user=os.environ.get('MYSQL_ADDON_USER', 'root'),
            password=os.environ.get('MYSQL_ADDON_PASSWORD', ''),
            database=os.environ.get('MYSQL_ADDON_DB', 'interest_calculator'),
            port=int(os.environ.get('MYSQL_ADDON_PORT', 3306))
        )
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
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        data = request.json
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
        
        return jsonify({'message': 'Investment updated successfully'})
    
    except Exception as e:
        print(f"Error updating investment: {e}")
        return jsonify({'error': 'Failed to update investment'}), 500

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
                  'Total (Compound)', 'Calculation Date']
        csv_data.append(','.join(headers))
        
        for inv in investments:
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
