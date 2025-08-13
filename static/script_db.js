// Interest Calculator Web Application with Database Storage
class InterestCalculator {
    constructor() {
        this.history = [];
        this.currentEditId = null;
        this.apiBaseUrl = window.location.origin + '/api';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setDefaultDate();
        this.loadHistory();
        this.updateResults();
    }

    setupEventListeners() {
        // Add Investment button
        document.getElementById('addInvestmentBtn').addEventListener('click', () => {
            this.addInvestment();
        });

        // Calculate button in edit modal
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

        // Modal close buttons
        document.querySelectorAll('.close').forEach(closeBtn => {
            closeBtn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal');
                if (modal) {
                    modal.style.display = 'none';
                }
            });
        });

        // Close modals when clicking outside
        window.addEventListener('click', (event) => {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        });

        // Enter key support for inputs
        document.querySelectorAll('input').forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    if (e.target.id === 'editEndDate') {
                        this.calculateInterest();
                    } else {
                        this.addInvestment();
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

    async addInvestment() {
        try {
            // Get input values
            const name = document.getElementById('name').value.trim();
            const principal = parseFloat(document.getElementById('principal').value);
            const rate = parseFloat(document.getElementById('rate').value);
            const startDate = document.getElementById('startDate').value;

            // Validate inputs
            if (!name) {
                this.showModal('Please enter a name.', 'error');
                return;
            }
            if (!principal || principal <= 0) {
                this.showModal('Please enter a valid principal amount.', 'error');
                return;
            }
            if (!rate || rate < 0) {
                this.showModal('Please enter a valid interest rate (per month).', 'error');
                return;
            }
            if (!startDate) {
                this.showModal('Please select a start date.', 'error');
                return;
            }

            // Create new investment (without end date)
            const investment = {
                id: Date.now(),
                name: name,
                principal: principal,
                rate: rate,
                startDate: startDate,
                endDate: '',
                months: 0,
                simpleInterest: 0,
                compoundInterest: 0,
                totalSimple: principal,
                totalCompound: principal,
                calculationDate: new Date().toISOString()
            };

            // Save to database
            const response = await fetch(`${this.apiBaseUrl}/investments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(investment)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            this.showModal('Investment added successfully! Add an ending date to calculate interest.', 'success');

            // Clear form
            document.getElementById('name').value = '';
            document.getElementById('principal').value = '';
            document.getElementById('rate').value = '';
            this.setDefaultDate();

            // Reload history
            await this.loadHistory();

        } catch (error) {
            console.error('Add investment error:', error);
            this.showModal(`Add investment error: ${error.message}`, 'error');
        }
    }

    editInvestment(id) {
        const investment = this.history.find(inv => inv.id === id);
        if (!investment) return;

        this.currentEditId = id;

        // Populate edit modal
        document.getElementById('editName').textContent = investment.name;
        document.getElementById('editPrincipal').textContent = this.formatCurrency(investment.principal);
        document.getElementById('editRate').textContent = `${investment.rate}% per month`;
        document.getElementById('editStartDate').textContent = investment.start_date;

        // Set default end date (start date + 1 month)
        const start = new Date(investment.start_date);
        const defaultEnd = new Date(start);
        defaultEnd.setMonth(defaultEnd.getMonth() + 1);
        document.getElementById('editEndDate').value = defaultEnd.toISOString().split('T')[0];

        // Show edit modal
        document.getElementById('editModal').style.display = 'block';
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

    async calculateInterest() {
        try {
            if (!this.currentEditId) {
                this.showModal('No investment selected for editing.', 'error');
                return;
            }

            const endDate = document.getElementById('editEndDate').value;
            if (!endDate) {
                this.showModal('Please select an ending date.', 'error');
                return;
            }

            const investment = this.history.find(inv => inv.id === this.currentEditId);
            if (!investment) {
                this.showModal('Investment not found.', 'error');
                return;
            }

            if (new Date(endDate) < new Date(investment.start_date)) {
                this.showModal('Ending date must be on or after the start date.', 'error');
                return;
            }

            // Calculate months between dates
            const months = Math.round(this.monthsBetween(investment.start_date, endDate) * 100) / 100;
            if (months <= 0) {
                this.showModal('The period must be at least part of a month.', 'error');
                return;
            }

            // Calculate interest using monthly rate
            const simpleInterest = Math.round((investment.principal * (investment.rate / 100) * months) * 100) / 100;
            const compoundInterest = Math.round((investment.principal * (Math.pow(1 + investment.rate / 100, months) - 1)) * 100) / 100;

            const totalSimple = Math.round((investment.principal + simpleInterest) * 100) / 100;
            const totalCompound = Math.round((investment.principal + compoundInterest) * 100) / 100;

            // Update in database
            const updateData = {
                endDate: endDate,
                months: months,
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound,
                calculationDate: new Date().toISOString()
            };

            const response = await fetch(`${this.apiBaseUrl}/investments/${this.currentEditId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updateData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Update results display
            this.updateResults({
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound
            });

            // Reload history
            await this.loadHistory();

            // Close modal and show success
            document.getElementById('editModal').style.display = 'none';
            this.showModal('Interest calculated successfully!', 'success');

            this.currentEditId = null;

        } catch (error) {
            console.error('Calculation error:', error);
            this.showModal(`Calculation error: ${error.message}`, 'error');
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

    async loadHistory() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/investments`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            this.history = await response.json();
            this.displayHistory();
        } catch (error) {
            console.error('Error loading history:', error);
            this.showModal(`Failed to load history: ${error.message}`, 'error');
        }
    }

    displayHistory() {
        const tbody = document.getElementById('historyTableBody');
        tbody.innerHTML = '';

        if (this.history.length === 0) {
            const row = tbody.insertRow();
            const cell = row.insertCell(0);
            cell.colSpan = 9;
            cell.textContent = 'No investments yet. Start by adding an investment!';
            cell.style.textAlign = 'center';
            cell.style.color = '#a0aec0';
            cell.style.padding = '40px';
            return;
        }

        // Debug: Log the first investment to see data structure
        if (this.history.length > 0) {
            console.log('First investment data:', this.history[0]);
        }

        this.history.forEach(inv => {
            const row = tbody.insertRow();

            row.insertCell(0).textContent = inv.name;
            row.insertCell(1).textContent = this.formatCurrency(inv.principal);
            row.insertCell(2).textContent = `${inv.rate}%/month`;
            row.insertCell(3).textContent = inv.start_date;
            row.insertCell(4).textContent = inv.end_date || '-';
            // Ensure numeric values and handle null/undefined
            const months = parseFloat(inv.months) || 0;
            const simpleInterest = parseFloat(inv.simple_interest) || 0;
            const compoundInterest = parseFloat(inv.compound_interest) || 0;

            row.insertCell(5).textContent = months > 0 ? months.toFixed(2) : '-';
            row.insertCell(6).textContent = simpleInterest > 0 ? this.formatCurrency(simpleInterest) : '-';
            row.insertCell(7).textContent = compoundInterest > 0 ? this.formatCurrency(compoundInterest) : '-';

            // Actions cell
            const actionsCell = row.insertCell(8);
            // Check if end_date exists and is not null/empty
            if (!inv.end_date || inv.end_date === null || inv.end_date === '') {
                // Show Edit button for investments without end date
                const editBtn = document.createElement('button');
                editBtn.textContent = 'Edit & Calculate';
                editBtn.className = 'edit-btn';
                editBtn.onclick = () => this.editInvestment(inv.id);
                actionsCell.appendChild(editBtn);
            } else {
                // Show calculated status
                actionsCell.textContent = 'Calculated';
                actionsCell.style.color = '#2f855a';
                actionsCell.style.fontWeight = '500';
            }
        });
    }

    async clearHistory() {
        if (confirm('Are you sure you want to clear all investment history? This action cannot be undone.')) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/investments`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error('Failed to clear history');
                }

                this.history = [];
                this.displayHistory();
                this.showModal('History cleared successfully!', 'success');
            } catch (error) {
                console.error('Error clearing history:', error);
                this.showModal('Failed to clear history.', 'error');
            }
        }
    }

    async exportToCSV() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/export`);
            if (!response.ok) {
                throw new Error('Failed to export data');
            }

            const data = await response.json();
            const csvContent = data.csv_data;

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
        } catch (error) {
            console.error('Error exporting data:', error);
            this.showModal('Failed to export data.', 'error');
        }
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

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
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

    document.getElementById('addInvestmentBtn').addEventListener('click', function () { animate(this); });
    document.getElementById('calculateBtn').addEventListener('click', function () { animate(this); });
});
