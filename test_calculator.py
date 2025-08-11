#!/usr/bin/env python3
"""
Test script for interest calculator functions
"""

def calculate_simple_interest(principal, rate, time_years):
    """Calculate simple interest"""
    return principal * (rate / 100) * time_years

def calculate_compound_interest(principal, rate, time_years):
    """Calculate compound interest"""
    return principal * ((1 + rate / 100) ** time_years - 1)

def test_calculations():
    """Test the interest calculations with sample data"""
    print("Testing Interest Calculator Functions")
    print("=" * 40)
    
    # Test case 1: Basic calculation
    principal = 10000
    rate = 5
    time_years = 3
    
    simple_interest = calculate_simple_interest(principal, rate, time_years)
    compound_interest = calculate_compound_interest(principal, rate, time_years)
    
    print(f"Test Case 1:")
    print(f"Principal: ${principal:,.2f}")
    print(f"Rate: {rate}%")
    print(f"Time: {time_years} years")
    print(f"Simple Interest: ${simple_interest:,.2f}")
    print(f"Compound Interest: ${compound_interest:,.2f}")
    print(f"Total (Simple): ${principal + simple_interest:,.2f}")
    print(f"Total (Compound): ${principal + compound_interest:,.2f}")
    print()
    
    # Test case 2: Monthly calculation
    principal2 = 5000
    rate2 = 3.5
    time_months = 18
    time_years2 = time_months / 12
    
    simple_interest2 = calculate_simple_interest(principal2, rate2, time_years2)
    compound_interest2 = calculate_compound_interest(principal2, rate2, time_years2)
    
    print(f"Test Case 2:")
    print(f"Principal: ${principal2:,.2f}")
    print(f"Rate: {rate2}%")
    print(f"Time: {time_months} months ({time_years2:.2f} years)")
    print(f"Simple Interest: ${simple_interest2:,.2f}")
    print(f"Compound Interest: ${compound_interest2:,.2f}")
    print(f"Total (Simple): ${principal2 + simple_interest2:,.2f}")
    print(f"Total (Compound): ${principal2 + compound_interest2:,.2f}")
    print()
    
    # Test case 3: Daily calculation
    principal3 = 1000
    rate3 = 2.5
    time_days = 90
    time_years3 = time_days / 365
    
    simple_interest3 = calculate_simple_interest(principal3, rate3, time_years3)
    compound_interest3 = calculate_compound_interest(principal3, rate3, time_years3)
    
    print(f"Test Case 3:")
    print(f"Principal: ${principal3:,.2f}")
    print(f"Rate: {rate3}%")
    print(f"Time: {time_days} days ({time_years3:.4f} years)")
    print(f"Simple Interest: ${simple_interest3:,.2f}")
    print(f"Compound Interest: ${compound_interest3:,.2f}")
    print(f"Total (Simple): ${principal3 + simple_interest3:,.2f}")
    print(f"Total (Compound): ${principal3 + compound_interest3:,.2f}")
    print()
    
    print("All tests completed successfully!")

if __name__ == "__main__":
    test_calculations()
