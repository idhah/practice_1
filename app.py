from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "mine-fuel-demo-secret"
DB = Path(__file__).with_name("fuel.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL,
        fuel_type TEXT NOT NULL,
        expected_lph REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS fuel_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER NOT NULL,
        operator TEXT NOT NULL,
        litres REAL NOT NULL,
        meter_reading REAL NOT NULL,
        issue_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(equipment_id) REFERENCES equipment(id)
    );
    CREATE TABLE IF NOT EXISTS fuel_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT NOT NULL,
        litres REAL NOT NULL,
        price_per_litre REAL NOT NULL,
        receipt_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO equipment(code,type,fuel_type,expected_lph) VALUES(?,?,?,?)",
            [
                ("DT-001", "Dump Truck", "Diesel", 28),
                ("EX-002", "Excavator", "Diesel", 20),
                ("LD-004", "Loader", "Diesel", 22),
            ],
        )
    conn.commit()
    conn.close()

@app.route("/")
def dashboard():
    conn = db()
    received = conn.execute("SELECT COALESCE(SUM(litres),0) FROM fuel_receipts").fetchone()[0]
    issued = conn.execute("SELECT COALESCE(SUM(litres),0) FROM fuel_issues").fetchone()[0]
    equipment = conn.execute("""
        SELECT e.*, COALESCE(SUM(f.litres),0) AS litres
        FROM equipment e LEFT JOIN fuel_issues f ON e.id=f.equipment_id
        GROUP BY e.id ORDER BY e.code
    """).fetchall()
    conn.close()
    return render_template("dashboard.html", received=received, issued=issued,
                           balance=received-issued, equipment=equipment)

@app.route("/equipment", methods=["GET", "POST"])
def equipment():
    conn = db()
    if request.method == "POST":
        try:
            conn.execute("INSERT INTO equipment(code,type,fuel_type,expected_lph) VALUES(?,?,?,?)",
                         (request.form["code"], request.form["type"],
                          request.form["fuel_type"], float(request.form["expected_lph"])))
            conn.commit()
            flash("Equipment added.")
        except sqlite3.IntegrityError:
            flash("Equipment code already exists.")
        return redirect(url_for("equipment"))
    rows = conn.execute("SELECT * FROM equipment ORDER BY code").fetchall()
    conn.close()
    return render_template("equipment.html", equipment=rows)

@app.route("/issue", methods=["GET", "POST"])
def issue():
    conn = db()
    if request.method == "POST":
        conn.execute("""INSERT INTO fuel_issues(equipment_id,operator,litres,meter_reading)
                        VALUES(?,?,?,?)""",
                     (request.form["equipment_id"], request.form["operator"],
                      float(request.form["litres"]), float(request.form["meter_reading"])))
        conn.commit()
        flash("Fuel issue recorded.")
        return redirect(url_for("issue"))
    equipment = conn.execute("SELECT * FROM equipment ORDER BY code").fetchall()
    issues = conn.execute("""
        SELECT f.*, e.code FROM fuel_issues f JOIN equipment e ON e.id=f.equipment_id
        ORDER BY f.id DESC LIMIT 20
    """).fetchall()
    conn.close()
    return render_template("issue.html", equipment=equipment, issues=issues)

@app.route("/receipt", methods=["GET", "POST"])
def receipt():
    conn = db()
    if request.method == "POST":
        conn.execute("""INSERT INTO fuel_receipts(supplier,litres,price_per_litre)
                        VALUES(?,?,?)""",
                     (request.form["supplier"], float(request.form["litres"]),
                      float(request.form["price_per_litre"])))
        conn.commit()
        flash("Fuel receipt recorded.")
        return redirect(url_for("receipt"))
    receipts = conn.execute("SELECT * FROM fuel_receipts ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return render_template("receipt.html", receipts=receipts)

@app.route("/reports")
def reports():
    conn = db()
    rows = conn.execute("""
        SELECT e.code, e.type, e.expected_lph,
               COALESCE(SUM(f.litres),0) AS litres,
               COUNT(f.id) AS transactions
        FROM equipment e LEFT JOIN fuel_issues f ON e.id=f.equipment_id
        GROUP BY e.id ORDER BY litres DESC
    """).fetchall()
    conn.close()
    return render_template("reports.html", rows=rows)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
