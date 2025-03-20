"""
DollarCheck - Personal Finance Tracker
A comprehensive personal finance management platform built with Python Flask.

Requirements:
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- Plotly
- Pandas
- Python-dotenv
- Werkzeug
"""

#######################
# Database Models (models.py)
#######################

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    budgets = db.relationship('Budget', backref='user', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expenses = db.relationship('Expense', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

#######################
# Authentication Routes (auth.py)
#######################

from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

auth = Blueprint('auth', __name__)

DEFAULT_CATEGORIES = [
    "Groceries",
    "Transportation",
    "Entertainment",
    "Bills",
    "Shopping",
    "Healthcare",
    "Other"
]

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Please check your login details and try again.')
    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('auth.register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(password, method='sha256')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Create default categories for the new user
        for category_name in DEFAULT_CATEGORIES:
            category = Category(name=category_name, user_id=new_user.id)
            db.session.add(category)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('main.dashboard'))
    
    return render_template('register.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

#######################
# Main Routes (routes.py)
#######################

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import plotly.express as px
import pandas as pd

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def dashboard():
    # Get all expenses for the current user
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    
    # Create expense summary for pie chart
    expense_data = []
    for category in categories:
        total = sum(expense.amount for expense in category.expenses)
        if total > 0:
            expense_data.append({
                'category': category.name,
                'amount': total
            })
    
    df = pd.DataFrame(expense_data)
    if not df.empty:
        fig = px.pie(df, values='amount', names='category', 
                     title='Expense Distribution',
                     color_discrete_sequence=px.colors.qualitative.Set3)
        chart = fig.to_html(full_html=False)
    else:
        chart = None
    
    return render_template('dashboard.html', 
                         expenses=expenses,
                         categories=categories,
                         budgets=budgets,
                         chart=chart)

@main.route('/expenses')
@login_required
def expenses():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    return render_template('expenses.html', categories=categories, expenses=expenses)

@main.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    amount = float(request.form.get('amount'))
    description = request.form.get('description')
    category_id = int(request.form.get('category_id'))
    date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
    
    expense = Expense(
        amount=amount,
        description=description,
        category_id=category_id,
        user_id=current_user.id,
        date=date
    )
    
    db.session.add(expense)
    db.session.commit()
    
    return redirect(url_for('main.expenses'))

@main.route('/budgets')
@login_required
def budgets():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    return render_template('budgets.html', categories=categories, budgets=budgets)

@main.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    amount = float(request.form.get('amount'))
    category_id = int(request.form.get('category_id'))
    month = datetime.now().strftime('%Y-%m')
    
    # Update existing budget or create new one
    budget = Budget.query.filter_by(
        category_id=category_id,
        user_id=current_user.id,
        month=month
    ).first()
    
    if budget:
        budget.amount = amount
    else:
        budget = Budget(
            amount=amount,
            category_id=category_id,
            user_id=current_user.id,
            month=month
        )
        db.session.add(budget)
    
    db.session.commit()
    return redirect(url_for('main.budgets'))

#######################
# Application Setup (app.py)
#######################

from flask import Flask
from flask_login import LoginManager
import os

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth)
app.register_blueprint(main)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)

"""
HTML Templates Structure:

templates/
├── base.html          # Base template with navigation and layout
├── login.html         # Login form
├── register.html      # Registration form
├── dashboard.html     # Main dashboard with expense charts
├── expenses.html      # Expense management page
└── budgets.html       # Budget management page

The HTML templates use Bootstrap for styling and include:
- Responsive navigation
- Forms for data input
- Charts for data visualization
- Tables for data display
- Proper error handling and flash messages

Each template extends base.html and includes specific content
for its functionality while maintaining consistent styling.
"""
