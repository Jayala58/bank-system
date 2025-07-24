from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = 'bank.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            loan_id TEXT PRIMARY KEY,
            customer_id TEXT,
            principal REAL,
            years INTEGER,
            interest_rate REAL,
            interest REAL,
            total_amount REAL,
            emi REAL,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id TEXT,
            amount REAL,
            payment_type TEXT,
            payment_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def generate_loan_id():
    return f"L{int(datetime.now().timestamp())}"

@app.route('/loan', methods=['POST'])
def lend_money():
    data = request.json
    customer_id = data['customer_id']
    P = data['loan_amount']
    N = data['loan_period']
    R = data['interest_rate']

    I = P * N * R / 100
    A = P + I
    EMI = round(A / (N * 12), 2)
    loan_id = generate_loan_id()

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO customers(id) VALUES (?)", (customer_id,))
    c.execute('''INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?)''',
              (loan_id, customer_id, P, N, R, I, A, EMI, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({
        "loan_id": loan_id,
        "total_amount": A,
        "monthly_emi": EMI
    })

@app.route('/payment', methods=['POST'])
def make_payment():
    data = request.json
    loan_id = data['loan_id']
    amount = data['amount']
    ptype = data['payment_type']

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT total_amount FROM loans WHERE loan_id = ?", (loan_id,))
    row = c.fetchone()
    if not row:
        return jsonify({"error": "Loan not found"}), 404

    total_amount = row[0]

    c.execute("SELECT SUM(amount) FROM payments WHERE loan_id = ?", (loan_id,))
    paid = c.fetchone()[0] or 0

    balance = total_amount - paid
    if amount > balance:
        return jsonify({"error": "Amount exceeds balance"}), 400

    c.execute('''INSERT INTO payments(loan_id, amount, payment_type, payment_date)
                 VALUES (?, ?, ?, ?)''', (loan_id, amount, ptype, datetime.now().isoformat()))
    conn.commit()

    c.execute("SELECT SUM(amount) FROM payments WHERE loan_id = ?", (loan_id,))
    total_paid = c.fetchone()[0] or 0

    conn.close()
    return jsonify({
        "message": "Payment successful",
        "remaining_balance": round(total_amount - total_paid, 2)
    })

@app.route('/ledger/<loan_id>', methods=['GET'])
def loan_ledger(loan_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT total_amount, emi FROM loans WHERE loan_id = ?", (loan_id,))
    loan = c.fetchone()
    if not loan:
        return jsonify({"error": "Loan not found"}), 404

    total_amount, emi = loan
    c.execute("SELECT amount, payment_type, payment_date FROM payments WHERE loan_id = ?", (loan_id,))
    transactions = [{"amount": r[0], "type": r[1], "date": r[2]} for r in c.fetchall()]

    c.execute("SELECT SUM(amount) FROM payments WHERE loan_id = ?", (loan_id,))
    paid = c.fetchone()[0] or 0
    balance = total_amount - paid
    emis_left = round(balance / emi)

    conn.close()
    return jsonify({
        "loan_id": loan_id,
        "transactions": transactions,
        "balance": round(balance, 2),
        "monthly_emi": emi,
        "emis_left": emis_left
    })

@app.route('/account/<customer_id>', methods=['GET'])
def account_overview(customer_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM loans WHERE customer_id = ?", (customer_id,))
    loans = c.fetchall()

    overview = []
    for loan in loans:
        loan_id, cust_id, P, N, R, I, A, EMI, _ = loan
        c.execute("SELECT SUM(amount) FROM payments WHERE loan_id = ?", (loan_id,))
        paid = c.fetchone()[0] or 0
        emis_left = round((A - paid) / EMI)
        overview.append({
            "loan_id": loan_id,
            "principal": P,
            "interest": I,
            "total_amount": A,
            "emi": EMI,
            "amount_paid": paid,
            "emis_left": emis_left
        })

    conn.close()
    return jsonify({
        "customer_id": customer_id,
        "loans": overview
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
