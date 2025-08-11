import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import sqlite3

class InterestCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Interest Calculator")
        self.root.geometry("700x500")
        
        # Initialize database
        self.init_database()
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(self.main_frame, text="Interest Calculator", 
                               font=('Arial', 20, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Input fields
        self.create_input_fields()
        
        # Calculate button
        calculate_btn = ttk.Button(self.main_frame, text="Calculate Interest", 
                                 command=self.calculate_interest)
        calculate_btn.grid(row=6, column=0, columnspan=2, pady=20)
        
        # Results frame
        self.create_results_frame()
        
        # History frame
        self.create_history_frame()
        
    def init_database(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect('interest_calculations.db')
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                principal_amount REAL NOT NULL,
                interest_rate REAL NOT NULL,
                time_period REAL NOT NULL,
                time_unit TEXT NOT NULL,
                start_date TEXT NOT NULL,
                simple_interest REAL NOT NULL,
                compound_interest REAL NOT NULL,
                total_amount_simple REAL NOT NULL,
                total_amount_compound REAL NOT NULL,
                calculation_date TEXT NOT NULL
            )
        ''')
        self.conn.commit()
        
    def create_input_fields(self):
        """Create input fields"""
        # Name field
        ttk.Label(self.main_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(self.main_frame, textvariable=self.name_var, width=30)
        name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Principal amount field
        ttk.Label(self.main_frame, text="Principal Amount ($):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.amount_var = tk.StringVar()
        amount_entry = ttk.Entry(self.main_frame, textvariable=self.amount_var, width=30)
        amount_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Interest rate field
        ttk.Label(self.main_frame, text="Interest Rate (%):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.rate_var = tk.StringVar()
        rate_entry = ttk.Entry(self.main_frame, textvariable=self.rate_var, width=30)
        rate_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        # Time period field
        ttk.Label(self.main_frame, text="Time Period:").grid(row=4, column=0, sticky=tk.W, pady=5)
        time_frame = ttk.Frame(self.main_frame)
        time_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
        self.time_var = tk.StringVar()
        time_entry = ttk.Entry(time_frame, textvariable=self.time_var, width=15)
        time_entry.pack(side=tk.LEFT)
        
        self.time_unit_var = tk.StringVar(value="years")
        time_unit_combo = ttk.Combobox(time_frame, textvariable=self.time_unit_var, 
                                      values=["years", "months", "days"], width=10, state="readonly")
        time_unit_combo.pack(side=tk.LEFT, padx=(10, 0))
        
        # Start date field
        ttk.Label(self.main_frame, text="Start Date:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.start_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        start_date_entry = ttk.Entry(self.main_frame, textvariable=self.start_date_var, width=30)
        start_date_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=5)
        
    def create_results_frame(self):
        """Create results display frame"""
        results_frame = ttk.LabelFrame(self.main_frame, text="Results", padding="10")
        results_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=20)
        
        self.simple_interest_label = ttk.Label(results_frame, text="Simple Interest: $0.00")
        self.simple_interest_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        self.compound_interest_label = ttk.Label(results_frame, text="Compound Interest: $0.00")
        self.compound_interest_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        self.total_simple_label = ttk.Label(results_frame, text="Total Amount (Simple): $0.00")
        self.total_simple_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        self.total_compound_label = ttk.Label(results_frame, text="Total Amount (Compound): $0.00")
        self.total_compound_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        
    def create_history_frame(self):
        """Create history display frame"""
        history_frame = ttk.LabelFrame(self.main_frame, text="Calculation History", padding="10")
        history_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=20)
        
        columns = ('Name', 'Principal', 'Rate', 'Period', 'Simple Interest', 'Date')
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=5)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100)
        
        self.history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Load history
        self.load_history()
        
    def calculate_interest(self):
        """Calculate interest"""
        try:
            # Validate inputs
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a name")
                return
                
            principal = float(self.amount_var.get())
            if principal <= 0:
                messagebox.showerror("Error", "Principal amount must be positive")
                return
                
            rate = float(self.rate_var.get())
            if rate < 0:
                messagebox.showerror("Error", "Interest rate cannot be negative")
                return
                
            time_period = float(self.time_var.get())
            if time_period <= 0:
                messagebox.showerror("Error", "Time period must be positive")
                return
                
            time_unit = self.time_unit_var.get()
            
            # Convert time to years
            if time_unit == "months":
                time_years = time_period / 12
            elif time_unit == "days":
                time_years = time_period / 365
            else:
                time_years = time_period
            
            # Calculate interest
            simple_interest = principal * (rate / 100) * time_years
            compound_interest = principal * ((1 + rate / 100) ** time_years - 1)
            
            total_simple = principal + simple_interest
            total_compound = principal + compound_interest
            
            # Update results
            self.simple_interest_label.config(text=f"Simple Interest: ${simple_interest:.2f}")
            self.compound_interest_label.config(text=f"Compound Interest: ${compound_interest:.2f}")
            self.total_simple_label.config(text=f"Total Amount (Simple): ${total_simple:.2f}")
            self.total_compound_label.config(text=f"Total Amount (Compound): ${total_compound:.2f}")
            
            # Save to database
            self.save_calculation(name, principal, rate, time_period, time_unit, 
                                simple_interest, compound_interest, total_simple, total_compound)
            
            # Refresh history
            self.load_history()
            
            messagebox.showinfo("Success", "Calculation completed!")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            
    def save_calculation(self, name, principal, rate, time_period, time_unit, 
                        simple_interest, compound_interest, total_simple, total_compound):
        """Save calculation to database"""
        self.cursor.execute('''
            INSERT INTO calculations 
            (name, principal_amount, interest_rate, time_period, time_unit, 
             start_date, simple_interest, compound_interest,
             total_amount_simple, total_amount_compound, calculation_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, principal, rate, time_period, time_unit, 
              self.start_date_var.get(), simple_interest, compound_interest,
              total_simple, total_compound, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        
    def load_history(self):
        """Load calculation history"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        self.cursor.execute('''
            SELECT name, principal_amount, interest_rate, time_period, 
                   simple_interest, calculation_date
            FROM calculations 
            ORDER BY calculation_date DESC 
            LIMIT 20
        ''')
        
        for row in self.cursor.fetchall():
            self.history_tree.insert('', 'end', values=(
                row[0], f"${row[1]:.2f}", f"{row[2]}%", f"{row[3]}",
                f"${row[4]:.2f}", row[5]
            ))
            
    def on_closing(self):
        """Handle application closing"""
        if hasattr(self, 'conn'):
            self.conn.close()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = InterestCalculator(root)
    
    # Set closing protocol
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    main()
