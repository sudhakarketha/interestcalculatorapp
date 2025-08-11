// Interest Calculator Web Application
class InterestCalculator {
    constructor() {
        this.history = JSON.parse(localStorage.getItem('interestCalculatorHistory')) || [];
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setDefaultDate();
        this.loadHistory();
        this.updateResults();
    }

    setupEventListeners() {
        // Step navigation
        const nextBtn = document.getElementById('nextBtn');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.validateStepOne()) {
                    // reveal end date and calculate button
                    document.getElementById('endDateContainer').style.display = 'block';
                    document.getElementById('calculateBtn').style.display = 'block';
                    document.getElementById('nextBtn').style.display = 'none';
                    // set default end date = start date + 1 month
                    const start = new Date(document.getElementById('startDate').value);
                    const defaultEnd = new Date(start);
                    defaultEnd.setMonth(defaultEnd.getMonth() + 1);
                    document.getElementById('endDate').value = defaultEnd.toISOString().split('T')[0];
                    this.showModal('Now choose an ending date and click Calculate.', 'info');
                }
            });
        }

        // Calculate button
        document.getElementById('calculateBtn').addEventListener('click', () => {
            this.calculateInterest();
        });

        // Clear history button
        document.getElementById('clearHistoryBtn').addEventListener('click', () => {
            this.clearHistory();
        });

        // Export button
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportToCSV();
        });

        // Modal close button
        document.querySelector('.close').addEventListener('click', () => {
            this.closeModal();
        });

        // Close modal when clicking outside
        window.addEventListener('click', (event) => {
            if (event.target === document.getElementById('modal')) {
                this.closeModal();
            }
        });

        // Enter key support for inputs
        document.querySelectorAll('input').forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    if (document.getElementById('calculateBtn').style.display === 'none') {
                        if (this.validateStepOne()) {
                            document.getElementById('nextBtn').click();
                        }
                    } else {
                        this.calculateInterest();
                    }
                }
            });
        });

        // Real-time validation
        document.getElementById('principal').addEventListener('input', () => {
            this.validateInput('principal');
        });

        document.getElementById('rate').addEventListener('input', () => {
            this.validateInput('rate');
        });

        document.getElementById('startDate').addEventListener('change', () => {
            const calcBtnVisible = document.getElementById('calculateBtn').style.display !== 'none';
            if (calcBtnVisible) {
                // Keep end date >= start date
                const start = new Date(document.getElementById('startDate').value);
                const endField = document.getElementById('endDate');
                if (endField.value) {
                    const end = new Date(endField.value);
                    if (end < start) {
                        endField.value = start.toISOString().split('T')[0];
                    }
                }
            }
        });

        document.getElementById('time')?.addEventListener('input', () => {
            this.validateInput('time');
        });
    }

    setDefaultDate() {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('startDate').value = today;
    }

    validateInput(fieldId) {
        const field = document.getElementById(fieldId);
        const value = parseFloat(field.value);

        if (fieldId === 'principal' && value <= 0) {
            field.style.borderColor = '#e53e3e';
            field.style.backgroundColor = '#fed7d7';
        } else if (fieldId === 'rate' && value < 0) {
            field.style.borderColor = '#e53e3e';
            field.style.backgroundColor = '#fed7d7';
        } else {
            field.style.borderColor = '#e2e8f0';
            field.style.backgroundColor = '#f7fafc';
        }
    }

    validateStepOne() {
        const name = document.getElementById('name').value.trim();
        const principal = parseFloat(document.getElementById('principal').value);
        const rate = parseFloat(document.getElementById('rate').value);
        const startDate = document.getElementById('startDate').value;

        if (!name) {
            this.showModal('Please enter a name.', 'error');
            return false;
        }
        if (!principal || principal <= 0) {
            this.showModal('Please enter a valid principal amount.', 'error');
            return false;
        }
        if (!rate || rate < 0) {
            this.showModal('Please enter a valid interest rate (per month).', 'error');
            return false;
        }
        if (!startDate) {
            this.showModal('Please select a start date.', 'error');
            return false;
        }
        return true;
    }

    monthsBetween(startDateStr, endDateStr) {
        const start = new Date(startDateStr);
        const end = new Date(endDateStr);
        if (end < start) return 0;

        let years = end.getFullYear() - start.getFullYear();
        let months = end.getMonth() - start.getMonth();
        let totalMonths = years * 12 + months;

        // fraction of month based on day difference
        const dayDiff = end.getDate() - start.getDate();
        totalMonths += dayDiff / 30; // approximate
        return totalMonths;
    }

    calculateInterest() {
        try {
            // Get input values
            const name = document.getElementById('name').value.trim();
            const principal = parseFloat(document.getElementById('principal').value);
            const rate = parseFloat(document.getElementById('rate').value); // percent per month
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;

            // Validate step two
            if (!endDate) {
                this.showModal('Please select an ending date.', 'error');
                return;
            }
            if (new Date(endDate) < new Date(startDate)) {
                this.showModal('Ending date must be on or after the start date.', 'error');
                return;
            }

            // Duration in months from dates
            const months = this.monthsBetween(startDate, endDate);
            if (months <= 0) {
                this.showModal('The period must be at least part of a month.', 'error');
                return;
            }

            // Calculate interest using monthly rate
            const simpleInterest = principal * (rate / 100) * months; // monthly simple
            const compoundInterest = principal * (Math.pow(1 + rate / 100, months) - 1); // monthly compounding

            const totalSimple = principal + simpleInterest;
            const totalCompound = principal + compoundInterest;

            // Update results display
            this.updateResults({
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound
            });

            // Save to history
            const calculation = {
                id: Date.now(),
                name: name,
                principal: principal,
                rate: rate,
                startDate: startDate,
                endDate: endDate,
                months: months,
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound,
                calculationDate: new Date().toLocaleString()
            };

            this.addToHistory(calculation);
            this.showModal('Interest calculation completed successfully!', 'success');

        } catch (error) {
            console.error('Calculation error:', error);
            this.showModal('An error occurred during calculation. Please check your inputs.', 'error');
        }
    }

    updateResults(results = null) {
        if (results) {
            document.getElementById('simpleInterest').textContent = this.formatCurrency(results.simpleInterest);
            document.getElementById('compoundInterest').textContent = this.formatCurrency(results.compoundInterest);
            document.getElementById('totalSimple').textContent = this.formatCurrency(results.totalSimple);
            document.getElementById('totalCompound').textContent = this.formatCurrency(results.totalCompound);
        } else {
            // Reset to default values
            document.getElementById('simpleInterest').textContent = '$0.00';
            document.getElementById('compoundInterest').textContent = '$0.00';
            document.getElementById('totalSimple').textContent = '$0.00';
            document.getElementById('totalCompound').textContent = '$0.00';
        }
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    addToHistory(calculation) {
        this.history.unshift(calculation);

        // Keep only last 50 calculations
        if (this.history.length > 50) {
            this.history = this.history.slice(0, 50);
        }

        this.saveHistory();
        this.loadHistory();
    }

    loadHistory() {
        const tbody = document.getElementById('historyTableBody');
        tbody.innerHTML = '';

        if (this.history.length === 0) {
            const row = tbody.insertRow();
            const cell = row.insertCell(0);
            cell.colSpan = 9;
            cell.textContent = 'No calculations yet. Start by calculating some interest!';
            cell.style.textAlign = 'center';
            cell.style.color = '#a0aec0';
            cell.style.padding = '40px';
            return;
        }

        this.history.forEach(calc => {
            const row = tbody.insertRow();

            row.insertCell(0).textContent = calc.name;
            row.insertCell(1).textContent = this.formatCurrency(calc.principal);
            row.insertCell(2).textContent = `${calc.rate}%/month`;
            row.insertCell(3).textContent = calc.startDate;
            row.insertCell(4).textContent = calc.endDate;
            row.insertCell(5).textContent = `${calc.months.toFixed(2)}`;
            row.insertCell(6).textContent = this.formatCurrency(calc.simpleInterest);
            row.insertCell(7).textContent = this.formatCurrency(calc.compoundInterest);
            row.insertCell(8).textContent = calc.calculationDate;
        });
    }

    clearHistory() {
        if (confirm('Are you sure you want to clear all calculation history? This action cannot be undone.')) {
            this.history = [];
            this.saveHistory();
            this.loadHistory();
            this.showModal('History cleared successfully!', 'success');
        }
    }

    exportToCSV() {
        if (this.history.length === 0) {
            this.showModal('No data to export.', 'error');
            return;
        }

        const headers = ['Name', 'Principal', 'Rate (% per month)', 'Start Date', 'End Date', 'Months', 'Simple Interest', 'Compound Interest', 'Total (Simple)', 'Total (Compound)', 'Calculation Date'];

        const csvContent = [
            headers.join(','),
            ...this.history.map(calc => [
                `"${calc.name}"`,
                calc.principal,
                `${calc.rate}%/month`,
                calc.startDate,
                calc.endDate,
                calc.months.toFixed(2),
                calc.simpleInterest,
                calc.compoundInterest,
                calc.totalSimple,
                calc.totalCompound,
                `"${calc.calculationDate}"`
            ].join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');

        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', `interest_calculations_${new Date().toISOString().split('T')[0]}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    saveHistory() {
        localStorage.setItem('interestCalculatorHistory', JSON.stringify(this.history));
    }

    showModal(message, type = 'info') {
        const modal = document.getElementById('modal');
        const modalMessage = document.getElementById('modalMessage');

        modalMessage.textContent = message;
        modalMessage.className = type;

        modal.style.display = 'block';

        // Auto-hide after 3 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                this.closeModal();
            }, 2000);
        }
    }

    closeModal() {
        document.getElementById('modal').style.display = 'none';
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new InterestCalculator();
});

// Add some additional utility functions
window.addEventListener('load', () => {
    // Add smooth scrolling for better UX
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add loading animation for buttons
    const animate = (el) => {
        el.style.transform = 'scale(0.98)';
        setTimeout(() => {
            el.style.transform = 'scale(1)';
        }, 120);
    };

    document.getElementById('calculateBtn').addEventListener('click', function () { animate(this); });
    const nextBtn = document.getElementById('nextBtn');
    if (nextBtn) nextBtn.addEventListener('click', function () { animate(this); });
});
