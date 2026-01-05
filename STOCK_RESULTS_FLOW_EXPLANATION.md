# How Stock Results Flow from .ipynb to Frontend

## Overview
This document explains the complete data flow from the Jupyter notebook (`.ipynb`) where the model is trained, to the Flask backend, and finally to the frontend display.

---

## 📊 **Step 1: Model Training in Jupyter Notebook** (`stock_pred.ipynb`)

### What Happens:
1. **Data Loading**: Stock data is loaded from Kaggle datasets
2. **Feature Engineering**: Technical indicators are calculated:
   - RSI (Relative Strength Index)
   - MACD (Moving Average Convergence Divergence)
   - Volatility (30-day and 90-day)
   - Bollinger Bands width
   - Momentum
   - Daily Return %

3. **Model Training**: XGBoost classifier is trained to predict risk levels:
   - **0** = Low Risk
   - **1** = Medium Risk
   - **2** = High Risk

4. **Model Saving**: The trained model is saved as:
   - `stock_risk_model.pkl` - The trained XGBoost model
   - `model_features.pkl` - List of feature names used

### Key Code (Cell 7):
```python
import joblib

# Save the model
joblib.dump(model, 'stock_risk_model.pkl')
joblib.dump(features, 'model_features.pkl')
```

---

## 🔄 **Step 2: Model Loading in Flask Backend** (`main.py`)

### What Happens:
When the Flask app starts, it loads the trained model from disk.

### Key Code (Lines 39-51):
```python
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
```

**Important**: The model is loaded once at startup and kept in memory for all requests.

---

## 📡 **Step 3: API Endpoint - Stock Analysis** (`/api/analyze-stock`)

### What Happens:
When a user requests stock analysis, the backend:

1. **Fetches Stock Data**: Uses `yfinance` to get recent stock data (last 180 days)
2. **Calculates Indicators**: Computes the same technical indicators used in training
3. **Makes Prediction**: Uses the loaded model to predict risk level
4. **Returns JSON**: Sends results back to frontend

### Key Code (Lines 235-303):

```python
@app.route('/api/analyze-stock', methods=['POST'])
@login_required
def analyze_stock():
    # 1. Get ticker from request
    ticker = data.get('ticker')
    
    # 2. Calculate technical indicators
    stock_data = calculate_stock_indicators(ticker)
    
    # 3. Prepare features in same order as training
    feature_values = [
        stock_data['RSI'],
        stock_data['MACD'],
        stock_data['Volatility_30'],
        stock_data['Volatility_90'],
        stock_data['BB_width'],
        stock_data['Momentum'],
        stock_data['Daily_Return_%']
    ]
    
    # 4. Make prediction
    prediction = stock_model.predict([feature_values])[0]  # Returns 0, 1, or 2
    probabilities = stock_model.predict_proba([feature_values])[0]  # Returns [prob_low, prob_med, prob_high]
    
    # 5. Format response
    risk_labels = ['Low Risk', 'Medium Risk', 'High Risk']
    colors = ['#10B981', '#F59E0B', '#EF4444']  # Green, Orange, Red
    
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
            'risk': risk_labels[prediction],  # "Low Risk", "Medium Risk", or "High Risk"
            'riskColor': colors[prediction],   # Color code for UI
            'probabilities': {
                'low': float(probabilities[0] * 100),      # Percentage
                'medium': float(probabilities[1] * 100),  # Percentage
                'high': float(probabilities[2] * 100)     # Percentage
            },
            'recommendation': '...'  # AI-generated recommendation
        }
    }
    
    return jsonify(result)
```

### Response Format:
```json
{
  "success": true,
  "data": {
    "price": 2450.50,
    "rsi": 65.23,
    "volatility": 1.85,
    "momentum": 2.5,
    "macd": 0.45,
    "bb_width": 25.3,
    "volatility_90": 1.92,
    "risk": "Low Risk",
    "riskColor": "#10B981",
    "probabilities": {
      "low": 95.2,
      "medium": 4.5,
      "high": 0.3
    },
    "recommendation": "This stock shows stable performance..."
  }
}
```

---

## 🎨 **Step 4: Frontend Display** (`templates/stocks.html`)

### What Happens:
The frontend JavaScript makes an AJAX request and displays the results.

### Key Code (Lines 289-348):

#### A. Making the Request:
```javascript
async function analyzeStock() {
    const ticker = stockSelect.value;  // e.g., "RELIANCE.NS"
    
    // Make API call
    const response = await fetch('/api/analyze-stock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker })
    });
    
    const result = await response.json();
    
    if (result.success) {
        displayAnalysis(result.data);  // Display the results
    }
}
```

#### B. Displaying the Results:
```javascript
function displayAnalysis(data) {
    // 1. Display Risk Badge (Large colored badge)
    document.getElementById('riskBadge').textContent = data.risk;  // "Low Risk"
    document.getElementById('riskBadge').style.background = data.riskColor;  // Green/Orange/Red
    
    // 2. Display Key Metrics
    document.getElementById('currentPrice').textContent = '₹' + data.price.toFixed(2);
    document.getElementById('rsiValue').textContent = data.rsi.toFixed(2);
    document.getElementById('volatility').textContent = data.volatility.toFixed(2) + '%';
    document.getElementById('momentum').textContent = data.momentum.toFixed(2) + '%';
    
    // 3. Display Recommendation
    document.getElementById('recommendationText').textContent = data.recommendation;
    
    // 4. Color-code momentum (green for positive, red for negative)
    const momentumEl = document.getElementById('momentum');
    momentumEl.style.color = data.momentum > 0 ? '#10B981' : '#EF4444';
}
```

### HTML Structure (Lines 56-101):
```html
<!-- Risk Assessment Badge -->
<div id="riskBadge" style="background: [color]; color: white;">
    Low Risk / Medium Risk / High Risk
</div>

<!-- Key Metrics Grid -->
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-label">Current Price</div>
        <div class="stat-value" id="currentPrice">₹2450.50</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">RSI (14)</div>
        <div class="stat-value" id="rsiValue">65.23</div>
    </div>
    <!-- ... more metrics ... -->
</div>

<!-- Recommendation Box -->
<div id="recommendation">
    <h4>💡 Investment Recommendation</h4>
    <p id="recommendationText">[AI-generated recommendation text]</p>
</div>
```

---

## 🔄 **Complete Data Flow Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Jupyter Notebook (stock_pred.ipynb)              │
│  ────────────────────────────────────────────────────────  │
│  1. Load stock data from Kaggle                            │
│  2. Calculate technical indicators                         │
│  3. Train XGBoost model                                    │
│  4. Save model: stock_risk_model.pkl                        │
│  5. Save features: model_features.pkl                     │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Flask Backend Startup (main.py)                   │
│  ────────────────────────────────────────────────────────  │
│  1. Load stock_risk_model.pkl into memory                   │
│  2. Load model_features.pkl into memory                    │
│  3. Keep model in memory for all requests                   │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: User Action (Frontend)                             │
│  ────────────────────────────────────────────────────────  │
│  User selects stock → Clicks "Analyze" button                │
│  JavaScript calls: analyzeStock()                           │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: API Request (stocks.html → main.py)               │
│  ────────────────────────────────────────────────────────  │
│  POST /api/analyze-stock                                    │
│  Body: { "ticker": "RELIANCE.NS" }                         │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Backend Processing (main.py)                       │
│  ────────────────────────────────────────────────────────  │
│  1. Fetch stock data from Yahoo Finance (yfinance)          │
│  2. Calculate indicators (RSI, MACD, Volatility, etc.)      │
│  3. Prepare feature array [RSI, MACD, Vol_30, ...]        │
│  4. Use loaded model: stock_model.predict([features])      │
│  5. Get probabilities: stock_model.predict_proba([features])│
│  6. Format response JSON                                    │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: API Response (JSON)                                 │
│  ────────────────────────────────────────────────────────  │
│  {                                                           │
│    "success": true,                                         │
│    "data": {                                                │
│      "risk": "Low Risk",                                    │
│      "riskColor": "#10B981",                               │
│      "price": 2450.50,                                      │
│      "rsi": 65.23,                                          │
│      "volatility": 1.85,                                    │
│      "probabilities": { "low": 95.2, ... }                 │
│    }                                                        │
│  }                                                           │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 7: Frontend Display (stocks.html)                    │
│  ────────────────────────────────────────────────────────  │
│  JavaScript receives JSON → displayAnalysis(data)          │
│  1. Update risk badge with color                            │
│  2. Display price, RSI, volatility, momentum                │
│  3. Show AI recommendation                                  │
│  4. Update UI elements with data                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 **Key Points**

1. **Model Training**: Done once in Jupyter notebook, saved as `.pkl` files
2. **Model Loading**: Happens once when Flask app starts
3. **Real-time Prediction**: Each stock analysis uses the loaded model
4. **Feature Consistency**: Same features must be calculated in same order
5. **JSON Communication**: Backend sends JSON, frontend displays it
6. **No Direct Connection**: Notebook and frontend don't communicate directly - Flask acts as intermediary

---

## 📝 **Files Involved**

| File | Purpose |
|------|---------|
| `stock_pred.ipynb` | Model training and saving |
| `stock_risk_model.pkl` | Trained XGBoost model (saved by notebook) |
| `model_features.pkl` | Feature names list (saved by notebook) |
| `main.py` | Flask backend - loads model, handles API requests |
| `templates/stocks.html` | Frontend UI - displays results |

---

## 🎯 **Example: Analyzing Reliance Stock**

1. **User Action**: Selects "Reliance Industries" from dropdown, clicks "Analyze"
2. **Frontend**: Sends `POST /api/analyze-stock` with `{"ticker": "RELIANCE.NS"}`
3. **Backend**: 
   - Fetches Reliance data from Yahoo Finance
   - Calculates: RSI=65.23, MACD=0.45, Volatility_30=1.85, etc.
   - Runs: `model.predict([[65.23, 0.45, 1.85, 1.92, 25.3, 2.5, 0.5]])` → Returns `0`
   - Maps `0` → "Low Risk" with color `#10B981`
4. **Response**: JSON with all data
5. **Frontend**: Displays green "Low Risk" badge, price ₹2450.50, RSI 65.23, etc.

---

This is how the trained model from your Jupyter notebook makes its way to the user interface! 🚀

