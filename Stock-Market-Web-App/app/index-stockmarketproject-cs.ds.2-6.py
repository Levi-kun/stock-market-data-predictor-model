#flask import statement
import yfinance as yf
##from datetime import outcome
#import time accesed from here from db?
#import db manager statement (need name of file) (import database as db), then

app = Flask(whatevername_itis)
app.key = 'trillion_dollar_stockmarket_predictor'

@app.route('/api/v1/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data['username']
    password = data['password']
    
    db_manager.add_user(username, password)
    return jsonify({'message': 'User signed up successfully!'})
#if ste error user or pswrd
    if not username or not password: 
        return jsonify({'error': 'Username and password are required!'})    
    
#seend to db
success = db_manager.add_user(username, password)
    if not success:
        return jsonify({'error': 'Username Already Exists!'})
    return jsonify({'message': 'User Signed up Successfully!'})

@app.route('/api/v1/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']
    
    if db_manager.verify_login(username, password):
        session['user'] = username #cookie
        return jsonify({'message': 'Login Successful', 'redirect': '/home'})
    else:
        return jsonify({'message': 'Invalid Credentials'})
@app.route('/home')
def home_page():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized. Please login.'})    
    return "Welcome to the Home Page (hom.html)"

@app.route('/index', methods=['POST'])#$$$$$$$$$$$
def get_stock_index():
    data = request.get_json()
    ticker = data.get('ticker')
    
    print(f"Processing request for: {ticker}")

    #2 week timer
    record = db_manager.get_stock_record(ticker)
    use_cache = False

    if record:
        last_date = datetime.strptime(record['date'], '%Y-%m-%d')#thanks gemini for the date function
        days_diff = (datetime.now() - last_date).days
        
        if days_diff < 14:
            use_cache = True
            print(f"Found fresh data in DB ({days_diff} days old).")

    if use_cache:
        return jsonify({'ticker': ticker,'ratio': record['ratio'],'source': 'database'})

    print("Data missing or old. Fetching from API...")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")

        if hist.empty:
            return jsonify({'error': 'Ticker not found'})

#ratio algorithm??? right? somewhere before
        today_str = datetime.now().strftime('%Y-%m-%d')
        db_manager.save_stock_record(ticker, ratio, today_str)

        return jsonify({'ticker': ticker,'ratio': ratio,'source': 'api_calculation'})
    
    #any statement if theres no internet or for whatever reasson yahoo has no data on the ticker or smth else??
