// Interest Calculator Web Application with Database Storage
class InterestCalculator {
    constructor() {
        this.history = [];
        this.currentEditId = null;
        this.apiBaseUrl = window.location.origin + '/api';
        this.currentUser = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setDefaultDate();
        this.loadHistory();
        this.fetchCurrentUser();
        // Don't clear results initially - will be set after loading history
    }
    
    fetchCurrentUser() {
        fetch(`${this.apiBaseUrl}/user`, {
            method: 'GET',
            credentials: 'include'
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Not authenticated');
        })
        .then(data => {
            this.currentUser = data.user;
            document.getElementById('username').textContent = this.currentUser.username;
        })
        .catch(error => {
            console.error('Error fetching user:', error);
            // Redirect to login page if not authenticated
            window.location.href = '/login';
        });
    }

    setupEventListeners() {
        // Add Investment button
        document.getElementById('addInvestmentBtn').addEventListener('click', () => {
            this.addInvestment();
        });
        
        // Logout button
        document.getElementById('logoutBtn').addEventListener('click', (e) => {
            e.preventDefault();
            this.logout();
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
    
    logout() {
        fetch(`${this.apiBaseUrl}/logout`, {
            method: 'POST',
            credentials: 'include'
        })
        .then(response => {
            if (response.ok) {
                // Redirect to login page after successful logout
                window.location.href = '/login';
            }
        })
        .catch(error => {
            console.error('Logout error:', error);
        });
    }

    async addInvestment() {
        try {
            // Get input values
            const name = document.getElementById('name').value.trim();
            const principal = parseFloat(document.getElementById('principal').value);
            const rate = parseFloat(document.getElementById('rate').value);
            const startDate = document.getElementById('startDate').value;
            const interestType = document.getElementById('interestType').value;

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
            if (!interestType) {
                this.showModal('Please select an interest type.', 'error');
                return;
            }

            // Create new investment (without end date)
            const investment = {
                id: Date.now(),
                name: name,
                principal: principal,
                rate: rate,
                startDate: startDate,
                interestType: interestType,
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
                body: JSON.stringify(investment),
                credentials: 'include'
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
        
        // Set interest type display and select value
        const interestTypeText = investment.interest_type === 'taken' ? 'Interest Taken (Loan)' : 'Interest Given (Lent)';
        document.getElementById('editInterestType').textContent = interestTypeText;
        document.getElementById('editInterestTypeSelect').value = investment.interest_type || 'taken';
        
        // Set interest type
        const interestType = investment.interest_type || 'taken';
        document.getElementById('editInterestType').textContent = interestType === 'taken' ? 'Interest Taken (Loan)' : 'Interest Given (Lent)';
        document.getElementById('editInterestTypeSelect').value = interestType;

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

            // Get selected interest type from edit modal
            const interestType = document.getElementById('editInterestTypeSelect').value;
            
            // Update in database
            const updateData = {
                endDate: endDate,
                months: months,
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound,
                interestType: interestType,
                calculationDate: new Date().toISOString()
            };

            const response = await fetch(`${this.apiBaseUrl}/investments/${this.currentEditId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updateData),
                credentials: 'include'
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Update results display with the calculated investment
            const updatedInvestment = {
                ...investment,
                end_date: endDate,
                months: months,
                simple_interest: simpleInterest,
                compound_interest: compoundInterest,
                total_simple: totalSimple,
                total_compound: totalCompound
            };

            this.updateResults({
                simpleInterest: simpleInterest,
                compoundInterest: compoundInterest,
                totalSimple: totalSimple,
                totalCompound: totalCompound
            }, updatedInvestment);

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

    updateResults(results = null, selectedInvestment = null) {
        console.log('updateResults called with:', { results, selectedInvestment }); // Debug log

        if (results && selectedInvestment) {
            // Show calculated results for a specific investment
            document.getElementById('simpleInterest').textContent = this.formatCurrency(results.simpleInterest);
            document.getElementById('compoundInterest').textContent = this.formatCurrency(results.compoundInterest);
            document.getElementById('totalSimple').textContent = this.formatCurrency(results.totalSimple);
            document.getElementById('totalCompound').textContent = this.formatCurrency(results.totalCompound);

            // Calculate and display total amount (principal + simple interest)
            const totalAmount = results.totalSimple;
            document.getElementById('totalAmount').textContent = this.formatCurrency(totalAmount);
        } else if (selectedInvestment && selectedInvestment.end_date) {
            // Show existing calculated results from database
            const months = parseFloat(selectedInvestment.months) || 0;
            const simpleInterest = parseFloat(selectedInvestment.simple_interest) || 0;
            const compoundInterest = parseFloat(selectedInvestment.compound_interest) || 0;
            const totalSimple = parseFloat(selectedInvestment.total_simple) || selectedInvestment.principal;
            const totalCompound = parseFloat(selectedInvestment.total_compound) || selectedInvestment.principal;

            document.getElementById('simpleInterest').textContent = this.formatCurrency(simpleInterest);
            document.getElementById('compoundInterest').textContent = this.formatCurrency(compoundInterest);
            document.getElementById('totalSimple').textContent = this.formatCurrency(totalSimple);
            document.getElementById('totalCompound').textContent = this.formatCurrency(totalCompound);
            document.getElementById('totalAmount').textContent = this.formatCurrency(totalSimple);
        } else if (selectedInvestment && !selectedInvestment.end_date) {
            // Show only principal for investments without end date
            document.getElementById('simpleInterest').textContent = this.formatCurrency(0);
            document.getElementById('compoundInterest').textContent = this.formatCurrency(0);
            document.getElementById('totalSimple').textContent = this.formatCurrency(selectedInvestment.principal);
            document.getElementById('totalCompound').textContent = this.formatCurrency(selectedInvestment.principal);
            document.getElementById('totalAmount').textContent = this.formatCurrency(selectedInvestment.principal);
        } else {
            // Show combined results from all investments
            this.updateResultsForAllInvestments();
        }
    }

    updateResultsForAllInvestments() {
        // Calculate combined totals from all investments
        let totalSimpleInterest = 0;
        let totalCompoundInterest = 0;
        let totalSimple = 0;
        let totalCompound = 0;
        let totalPrincipal = 0;

        this.history.forEach(inv => {
            const simpleInterest = parseFloat(inv.simple_interest) || 0;
            const compoundInterest = parseFloat(inv.compound_interest) || 0;
            const totalSimpleInv = parseFloat(inv.total_simple) || inv.principal;
            const totalCompoundInv = parseFloat(inv.total_compound) || inv.principal;

            totalSimpleInterest += simpleInterest;
            totalCompoundInterest += compoundInterest;
            totalSimple += totalSimpleInv;
            totalCompound += totalCompoundInv;
            totalPrincipal += inv.principal;
        });

        // Display combined results
        document.getElementById('simpleInterest').textContent = this.formatCurrency(totalSimpleInterest);
        document.getElementById('compoundInterest').textContent = this.formatCurrency(totalCompoundInterest);
        document.getElementById('totalSimple').textContent = this.formatCurrency(totalSimple);
        document.getElementById('totalCompound').textContent = this.formatCurrency(totalCompound);
        document.getElementById('totalAmount').textContent = this.formatCurrency(totalSimple);

        // Show info about all investments
        const infoDiv = document.getElementById('selectedInvestmentInfo');
        const nameSpan = document.getElementById('selectedInvestmentName');
        const detailsSpan = document.getElementById('selectedInvestmentDetails');

        if (infoDiv && nameSpan && detailsSpan) {
            nameSpan.textContent = `All Investments (${this.history.length} total)`;
            detailsSpan.textContent = `Combined results from all investments in the portfolio`;
            infoDiv.style.display = 'block';
        }
    }

    async loadHistory() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/investments`, {
                credentials: 'include'
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            this.history = await response.json();
            this.displayHistory();
            // Show combined results from all investments initially
            this.updateResultsForAllInvestments();
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
            cell.colSpan = 10;
            cell.textContent = 'No investments yet. Start by adding an investment!';
            cell.style.textAlign = 'center';
            cell.style.color = '#a0aec0';
            cell.style.padding = '40px';
            return;
        }
        
        // Helper function to get interest type display text
        const getInterestTypeText = (type) => {
            return type === 'taken' ? 'Interest Taken (Loan)' : 'Interest Given (Lent)';
        };

        // Debug: Log the first investment to see data structure
        if (this.history.length > 0) {
            console.log('First investment data:', this.history[0]);
        }

        this.history.forEach(investment => {
            const hasCalculation = investment.end_date && investment.months > 0;
            const statusClass = hasCalculation ? 'calculated' : 'pending';
            const statusText = hasCalculation ? 'Calculated' : 'Pending';
            const interestTypeText = getInterestTypeText(investment.interest_type || 'taken');

            const row = tbody.insertRow();
            row.setAttribute('data-id', investment.id);
            row.classList.add(statusClass);
            
            row.insertCell(0).textContent = investment.name;
            row.insertCell(1).textContent = this.formatCurrency(investment.principal);
            row.insertCell(2).textContent = `${investment.rate}%`;
            row.insertCell(3).textContent = investment.start_date;
            row.insertCell(4).textContent = hasCalculation ? investment.end_date : '-';
            row.insertCell(5).textContent = hasCalculation ? investment.months : '-';
            row.insertCell(6).textContent = hasCalculation ? this.formatCurrency(investment.simple_interest) : '-';
            row.insertCell(7).textContent = hasCalculation ? this.formatCurrency(investment.compound_interest) : '-';
            row.insertCell(8).textContent = hasCalculation ? this.formatCurrency(investment.total_simple) : this.formatCurrency(investment.principal);
            
            // Actions cell
            const actionsCell = row.insertCell(9);
            const editBtn = document.createElement('button');
            editBtn.className = 'edit-btn';
            editBtn.innerHTML = '<i class="fas fa-calculator"></i>';
            editBtn.title = 'Calculate Interest';
            editBtn.onclick = (e) => {
                e.stopPropagation();
                this.editInvestment(investment.id);
            };
            actionsCell.appendChild(editBtn);
            
            // Add delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            deleteBtn.title = 'Delete Investment';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                this.deleteInvestment(investment.id, investment.name);
            };
            actionsCell.appendChild(deleteBtn);
        });
        
        // Make rows clickable to select investment and show results
        document.querySelectorAll('#historyTableBody tr').forEach(row => {
            row.style.cursor = 'pointer';
            row.onclick = (e) => {
                const id = row.getAttribute('data-id');
                const investment = this.history.find(inv => inv.id === parseInt(id));
                console.log('Row clicked for investment:', investment?.name); // Debug log
                if (investment) {
                    this.selectInvestment(investment);
                }
            };

            // Double-click to deselect and show all investments
            row.ondblclick = (e) => {
                console.log('Row double-clicked - deselecting'); // Debug log
                this.deselectInvestment();
            };

            // Add hover effect
            row.onmouseenter = () => {
                row.style.backgroundColor = '#f7fafc';
            };
            row.onmouseleave = () => {
                row.style.backgroundColor = '';
            };

        });
    }

    selectInvestment(investment) {
        console.log('selectInvestment called for:', investment.name); // Debug log

        // Highlight the selected row
        const tbody = document.getElementById('historyTableBody');
        const rows = tbody.querySelectorAll('tr');

        rows.forEach(row => {
            row.style.backgroundColor = '';
            row.style.borderLeft = '';
        });

        // Find and highlight the clicked row
        const clickedRow = Array.from(rows).find(row => {
            const nameCell = row.cells[0];
            return nameCell && nameCell.textContent === investment.name;
        });

        if (clickedRow) {
            clickedRow.style.backgroundColor = '#e6f3ff';
            clickedRow.style.borderLeft = '4px solid #667eea';
        }

        // Update results based on the selected investment
        this.updateResults(null, investment);

        // Update the selected investment info display
        this.updateSelectedInvestmentInfo(investment);

        // Show a brief message about what's displayed
        if (investment.end_date) {
            this.showModal(`Showing results for "${investment.name}" - ${investment.months} months (Double-click to show all investments)`, 'info');
        } else {
            this.showModal(`Selected "${investment.name}" - Add end date to calculate interest (Double-click to show all investments)`, 'info');
        }
    }

    updateSelectedInvestmentInfo(investment) {
        const infoDiv = document.getElementById('selectedInvestmentInfo');
        const nameSpan = document.getElementById('selectedInvestmentName');
        const detailsSpan = document.getElementById('selectedInvestmentDetails');

        if (investment) {
            nameSpan.textContent = investment.name;
            
            const interestTypeText = investment.interest_type === 'taken' ? 'Interest Taken (Loan)' : 'Interest Given (Lent)';

            if (investment.end_date) {
                const months = parseFloat(investment.months) || 0;
                detailsSpan.textContent = `Principal: ${this.formatCurrency(investment.principal)} | Rate: ${investment.rate}%/month | Type: ${interestTypeText} | Period: ${months.toFixed(2)} months`;
            } else {
                detailsSpan.textContent = `Principal: ${this.formatCurrency(investment.principal)} | Rate: ${investment.rate}%/month | Type: ${interestTypeText} | Start Date: ${investment.start_date}`;
            }

            infoDiv.style.display = 'block';
        } else {
            infoDiv.style.display = 'none';
        }
    }

    deselectInvestment() {
        // Remove highlighting from all rows
        const tbody = document.getElementById('historyTableBody');
        const rows = tbody.querySelectorAll('tr');

        rows.forEach(row => {
            row.style.backgroundColor = '';
            row.style.borderLeft = '';
        });

        // Show combined results from all investments
        this.updateResultsForAllInvestments();

        // Show a brief message
        this.showModal('Showing combined results from all investments', 'info');
    }

    async deleteInvestment(investmentId, investmentName) {
        if (confirm(`Are you sure you want to delete the investment "${investmentName}"? This action cannot be undone.`)) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/investments/${investmentId}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                }

                // Remove from local history
                this.history = this.history.filter(inv => inv.id !== investmentId);
                this.displayHistory();
                this.showModal(`Investment "${investmentName}" deleted successfully!`, 'success');
            } catch (error) {
                console.error('Error deleting investment:', error);
                this.showModal(`Failed to delete investment: ${error.message}`, 'error');
            }
        }
    }

    async clearHistory() {
        if (confirm('Are you sure you want to clear all investment history? This action cannot be undone.')) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/investments`, {
                    method: 'DELETE',
                    credentials: 'include'
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
            const response = await fetch(`${this.apiBaseUrl}/export`, {
                credentials: 'include'
            });
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
        return '₹' + new Intl.NumberFormat('en-IN', {
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
    // Mobile Navigation Toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
            navToggle.classList.toggle('active');
        });
    }

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

                // Close mobile menu if open
                if (navMenu && navMenu.classList.contains('active')) {
                    navMenu.classList.remove('active');
                    navToggle.classList.remove('active');
                }
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

    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            if (window.scrollY > 100) {
                navbar.style.background = 'rgba(255, 255, 255, 0.98)';
                navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.15)';
            } else {
                navbar.style.background = 'rgba(255, 255, 255, 0.95)';
                navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
            }
        }
    });
});
