import os
from flask import Flask, render_template, redirect, url_for
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    totals = {}
    for table, label in [("companies", "Companies"), ("jobs", "Jobs"),
                         ("applications", "Applications"), ("contacts", "Contacts")]:
        cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
        totals[label] = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT status, COUNT(*) AS total
        FROM applications
        GROUP BY status
        ORDER BY total DESC
    """)
    status_counts = cursor.fetchall()

    cursor.execute("""
        SELECT j.job_title, c.company_name, a.application_date, a.status
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        ORDER BY a.application_date DESC
        LIMIT 5
    """)
    recent = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("dashboard.html", totals=totals,
                           status_counts=status_counts, recent=recent)


if __name__ == "__main__":
    app.run(debug=True)