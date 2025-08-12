// Interest Calculator Web Application
class InterestCalculator {
    constructor() {
        this.history = JSON.parse(localStorage.getItem('interestCalculatorHistory')) || [];
        this.currentEditId = null;
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

    addInvestment() {
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
                calculationDate: new Date().toLocaleString()
            };

            this.addToHistory(investment);
            this.showModal('Investment added successfully! Add an ending date to calculate interest.', 'success');

            // Clear form
            document.getElementById('name').value = '';
            document.getElementById('principal').value = '';
            document.getElementById('rate').value = '';
            this.setDefaultDate();

        } catch (error) {
            console.error('Add investment error:', error);
            this.showModal('An error occurred. Please check your inputs.', 'error');
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
        document.getElementById('editStartDate').textContent = investment.startDate;

        // Set default end date (start date + 1 month)
        const start = new Date(investment.startDate);
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

    calculateInterest() {
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

            if (new Date(endDate) < new Date(investment.startDate)) {
                this.showModal('Ending date must be on or after the start date.', 'error');
                return;
            }

            // Calculate months between dates
            const months = this.monthsBetween(investment.startDate, endDate);
            if (months <= 0) {
                this.showModal('The period must be at least part of a month.', 'error');
                return;
            }

            // Calculate interest using monthly rate
            const simpleInterest = investment.principal * (investment.rate / 100) * months;
            const compoundInterest = investment.principal * (Math.pow(1 + investment.rate / 100, months) - 1);

            const totalSimple = investment.principal + simpleInterest;
            const totalCompound = investment.principal + compoundInterest;

            // Update the investment
            investment.endDate = endDate;
            investment.months = months;
            investment.simpleInterest = simpleInterest;
            investment.compoundInterest = compoundInterest;
            investment.totalSimple = totalSimple;
            investment.totalCompound = totalCompound;
            investment.calculationDate = new Date().toLocaleString();

            // Update results display
            this.updateResults({
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound
            });

            // Save and refresh
            this.saveHistory();
            this.loadHistory();

            // Close modal and show success
            document.getElementById('editModal').style.display = 'none';
            this.showModal('Interest calculated successfully!', 'success');

            this.currentEditId = null;

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

    addToHistory(investment) {
        this.history.unshift(investment);

        // Keep only last 50 investments
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
            cell.textContent = 'No investments yet. Start by adding an investment!';
            cell.style.textAlign = 'center';
            cell.style.color = '#a0aec0';
            cell.style.padding = '40px';
            return;
        }

        this.history.forEach(inv => {
            const row = tbody.insertRow();

            row.insertCell(0).textContent = inv.name;
            row.insertCell(1).textContent = this.formatCurrency(inv.principal);
            row.insertCell(2).textContent = `${inv.rate}%/month`;
            row.insertCell(3).textContent = inv.startDate;
            row.insertCell(4).textContent = inv.endDate || '-';
            row.insertCell(5).textContent = inv.months > 0 ? inv.months.toFixed(2) : '-';
            row.insertCell(6).textContent = inv.simpleInterest > 0 ? this.formatCurrency(inv.simpleInterest) : '-';
            row.insertCell(7).textContent = inv.compoundInterest > 0 ? this.formatCurrency(inv.compoundInterest) : '-';

            // Actions cell
            const actionsCell = row.insertCell(8);
            if (!inv.endDate) {
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

    clearHistory() {
        if (confirm('Are you sure you want to clear all investment history? This action cannot be undone.')) {
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
            ...this.history.map(inv => [
                `"${inv.name}"`,
                inv.principal,
                `${inv.rate}%/month`,
                inv.startDate,
                inv.endDate || '',
                inv.months > 0 ? inv.months.toFixed(2) : '',
                inv.simpleInterest > 0 ? inv.simpleInterest : '',
                inv.compoundInterest > 0 ? inv.compoundInterest : '',
                inv.totalSimple,
                inv.totalCompound,
                `"${inv.calculationDate}"`
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

    document.getElementById('addInvestmentBtn').addEventListener('click', function () { animate(this); });
    document.getElementById('calculateBtn').addEventListener('click', function () { animate(this); });
});
