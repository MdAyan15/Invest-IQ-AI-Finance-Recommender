from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import yfinance as yf
import joblib
import pandas as pd
from ta import momentum, trend, volatility
import requests
from functools import wraps
import os
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///investiq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configure Gemini API using the correct SDK
gemini_api_key = os.getenv('GEMINI_API_KEY')
gemini_client = None

if gemini_api_key:
    try:
        gemini_client = genai.Client(api_key=gemini_api_key)
        print("✅ ChatGPT API configured successfully!")
    except Exception as e:
        gemini_client = None
        print(f"⚠️ Warning: Could not configure ChatGPT API: {e}")
else:
    print("⚠️ Warning: GEMINI_API_KEY not found in environment variables")

# Load stock model
try:
    model_path = r'D:\Major Project\stock_risk_model (1).pkl'
    stock_model = joblib.load(model_path)
    
    features_path = r'D:\Major Project\model_features (1).pkl'
    model_features = joblib.load(features_path)
    
    print("✅ Stock model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load stock model: {e}")
    stock_model = None
    model_features = None

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer)
    monthly_income = db.Column(db.Float, default=0)
    monthly_expenses = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    savings_history = db.relationship('SavingsHistory', backref='user', lazy=True)

class SavingsHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month_year = db.Column(db.String(20))
    income = db.Column(db.Float)
    expenses = db.Column(db.Float)
    savings = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Stock analysis helper function
def calculate_stock_indicators(ticker):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        
        if df.empty or len(df) < 100:
            return None
        
        # Calculate technical indicators
        df['RSI'] = momentum.rsi(df['Close'], window=14)
        df['MACD'] = trend.macd_diff(df['Close'])
        
        bb_high = volatility.bollinger_hband(df['Close'])
        bb_low = volatility.bollinger_lband(df['Close'])
        df['BB_width'] = bb_high - bb_low
        
        df['Daily_Return_%'] = df['Close'].pct_change() * 100
        df['Volatility_30'] = df['Daily_Return_%'].rolling(window=30).std()
        df['Volatility_90'] = df['Daily_Return_%'].rolling(window=90).std()
        df['Momentum'] = df['Close'].pct_change(periods=10) * 100
        
        latest = df.iloc[-1]
        
        if pd.isna(latest['RSI']) or pd.isna(latest['Volatility_30']) or pd.isna(latest['Volatility_90']):
            return None
        
        return {
            'ticker': ticker,
            'close': float(latest['Close']),
            'RSI': float(latest['RSI']),
            'MACD': float(latest['MACD']),
            'Volatility_30': float(latest['Volatility_30']),
            'Volatility_90': float(latest['Volatility_90']),
            'BB_width': float(latest['BB_width']),
            'Momentum': float(latest['Momentum']),
            'Daily_Return_%': float(latest['Daily_Return_%'])
        }
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        return None

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        age = request.form.get('age')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password=hashed_password, age=age)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    savings = user.monthly_income - user.monthly_expenses
    savings_rate = (savings / user.monthly_income * 100) if user.monthly_income > 0 else 0
    
    return render_template('dashboard.html', user=user, savings=savings, savings_rate=savings_rate)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user = User.query.get(session['user_id'])
    
    user.age = request.form.get('age')
    user.monthly_income = float(request.form.get('income'))
    user.monthly_expenses = float(request.form.get('expenses'))
    
    # Save to history
    savings = user.monthly_income - user.monthly_expenses
    history = SavingsHistory(
        user_id=user.id,
        month_year=datetime.now().strftime('%Y-%m'),
        income=user.monthly_income,
        expenses=user.monthly_expenses,
        savings=savings
    )
    
    db.session.add(history)
    db.session.commit()
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('savings'))

@app.route('/savings')
@login_required
def savings():
    user = User.query.get(session['user_id'])
    history = SavingsHistory.query.filter_by(user_id=user.id).order_by(SavingsHistory.created_at.desc()).limit(12).all()
    
    return render_template('savings.html', user=user, history=history)

@app.route('/stocks')
@login_required
def stocks():
    return render_template('stocks.html')

@app.route('/api/analyze-stock', methods=['POST'])
@login_required
def analyze_stock():
    try:
        data = request.json
        ticker = data.get('ticker')
        
        if not ticker:
            return jsonify({'success': False, 'error': 'No ticker provided'}), 400
        
        # Calculate indicators
        stock_data = calculate_stock_indicators(ticker)
        
        if not stock_data:
            return jsonify({'success': False, 'error': 'Could not fetch stock data'}), 400
        
        # Use your trained model for prediction
        if stock_model is not None:
            feature_values = [
                stock_data['RSI'],
                stock_data['MACD'],
                stock_data['Volatility_30'],
                stock_data['Volatility_90'],
                stock_data['BB_width'],
                stock_data['Momentum'],
                stock_data['Daily_Return_%']
            ]
            
            prediction = stock_model.predict([feature_values])[0]
            probabilities = stock_model.predict_proba([feature_values])[0]
            
            risk_labels = ['Low Risk', 'Medium Risk', 'High Risk']
            colors = ['#10B981', '#F59E0B', '#EF4444']
            
            result = {
                'success': True,
                'data': {
                    'price': stock_data['close'],
                    'rsi': stock_data['RSI'],
                    'volatility': stock_data['Volatility_30'],
                    'momentum': stock_data['Momentum'],
                    'macd': stock_data['MACD'],
                    'bb_width': stock_data['BB_width'],
                    'volatility_90': stock_data['Volatility_90'],
                    'risk': risk_labels[prediction],
                    'riskColor': colors[prediction],
                    'probabilities': {
                        'low': float(probabilities[0] * 100),
                        'medium': float(probabilities[1] * 100),
                        'high': float(probabilities[2] * 100)
                    }
                }
            }
            
            # Add recommendation based on model prediction
            if prediction == 0:
                result['data']['recommendation'] = 'This stock shows stable performance with low volatility. Suitable for conservative investors looking for steady returns. The AI model indicates low risk based on technical indicators.'
            elif prediction == 1:
                result['data']['recommendation'] = 'This stock shows moderate risk characteristics. Suitable for balanced portfolios. The AI model suggests monitoring closely and maintaining proper position sizing.'
            else:
                result['data']['recommendation'] = 'This stock exhibits high volatility. Suitable only for aggressive investors with high risk tolerance. The AI model indicates significant risk - exercise caution.'
            
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Model not loaded'}), 500
            
    except Exception as e:
        print(f"Error in analyze_stock: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/mutual-funds')
@login_required
def mutual_funds():
    return render_template('mutual_funds.html')

@app.route('/sip-calculator')
@login_required
def sip_calculator():
    return render_template('sip_calculator.html')

@app.route('/api/calculate-sip', methods=['POST'])
@login_required
def calculate_sip():
    data = request.json
    monthly_sip = float(data['monthly_sip'])
    expected_return = float(data['expected_return'])
    time_period = int(data['time_period'])
    
    monthly_rate = expected_return / 12 / 100
    months = time_period * 12
    
    if monthly_rate > 0:
        future_value = monthly_sip * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
    else:
        future_value = monthly_sip * months
    
    total_invested = monthly_sip * months
    total_returns = future_value - total_invested
    
    return jsonify({
        'total_invested': round(total_invested, 2),
        'total_returns': round(total_returns, 2),
        'future_value': round(future_value, 2)
    })

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'No message provided'}), 400
        
        if not gemini_client:
            return jsonify({
                'success': False, 
                'error': 'Gemini API not configured. Please add GEMINI_API_KEY to .env file'
            }), 500
        
        # Create context for financial advisor
        context = """You are InvestIQ, an AI financial advisor assistant. 
        Help users with questions about:
        - Stock market and investments
        - Mutual funds and SIPs
        - Savings strategies and budgeting
        - Financial planning and wealth management
        - Risk assessment and portfolio diversification
        
        Provide clear, helpful, and educational advice. Keep responses concise and actionable.
        Always remind users that this is educational information, not professional financial advice.
        Be friendly, professional, and encouraging."""
        
        full_prompt = f"{context}\n\nUser question: {user_message}\n\nProvide a helpful response:"
        
        # Generate response using Gemini with correct SDK
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        
        assistant_response = response.text
        
        return jsonify({
            'success': True,
            'response': assistant_response
        })
        
    except Exception as e:
        print(f"Error in chat: {e}")
        return jsonify({
            'success': False,
            'error': f"Error generating response: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)