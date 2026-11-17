import os
import mysql.connector
from flask import Flask, render_template, redirect, url_for, request, flash
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# DASHBOARD SECTION

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
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

        return render_template("dashboard.html", totals=totals,
                               status_counts=status_counts, recent=recent)
    finally:
        cursor.close()
        conn.close()

# HELPER FUNCTIONS
def clean(value):
    """Strip spaces; turn empty strings into None (NULL in MySQL)."""
    value = (value or "").strip()
    return value or None


# COMPANY SECTION

COMPANY_FIELDS = ["company_name", "industry", "website", "city", "state", "notes"]


def get_company_form():
    data = {field: clean(request.form.get(field)) for field in COMPANY_FIELDS}
    errors = []

    if not data["company_name"]:
        errors.append("Company name is required.")

    limits = {"company_name": 100, "industry": 50, "website": 200, "city": 50, "state": 50}
    for field, limit in limits.items():
        if data[field] and len(data[field]) > limit:
            label = field.replace("_", " ").capitalize()
            errors.append(f"{label} must be {limit} characters or fewer.")

    if data["website"] and not data["website"].startswith(("http://", "https://")):
        errors.append("Website must start with http:// or https://")

    return data, errors


def render_companies_page(form=None, edit_id=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM companies ORDER BY company_name")
        companies = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template("companies.html", companies=companies,
                           form=form or {}, edit_id=edit_id, detail=None)


@app.route("/companies")
def companies():
    return render_companies_page()


@app.route("/companies/<int:company_id>")
def company_detail(company_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM companies WHERE company_id = %s", (company_id,))
        company = cursor.fetchone()
        if company is None:
            flash("Company not found.", "warning")
            return redirect(url_for("companies"))

        cursor.execute("SELECT job_id, job_title, job_type FROM jobs WHERE company_id = %s",
                       (company_id,))
        jobs = cursor.fetchall()

        cursor.execute("SELECT contact_id, contact_name, title, email FROM contacts WHERE company_id = %s",
                       (company_id,))
        contacts = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template("companies.html", detail=company, jobs=jobs, contacts=contacts)


@app.route("/companies/add", methods=["POST"])
def add_company():
    data, errors = get_company_form()
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_companies_page(form=data)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO companies (company_name, industry, website, city, state, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [data[f] for f in COMPANY_FIELDS])
        conn.commit()
        flash(f"Company '{data['company_name']}' added.", "success")
    except mysql.connector.Error as err:
        flash(f"Database error: {err.msg}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("companies"))


@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def edit_company(company_id):
    if request.method == "POST":
        data, errors = get_company_form()
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_companies_page(form=data, edit_id=company_id)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE companies
                SET company_name = %s, industry = %s, website = %s,
                    city = %s, state = %s, notes = %s
                WHERE company_id = %s
            """, [data[f] for f in COMPANY_FIELDS] + [company_id])
            conn.commit()
            flash(f"Company '{data['company_name']}' updated.", "success")
        except mysql.connector.Error as err:
            flash(f"Database error: {err.msg}", "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for("companies"))

    # GET: load the company into the form
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM companies WHERE company_id = %s", (company_id,))
        company = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if company is None:
        flash("Company not found.", "warning")
        return redirect(url_for("companies"))
    return render_companies_page(form=company, edit_id=company_id)


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM companies WHERE company_id = %s", (company_id,))
        conn.commit()
        if cursor.rowcount:
            flash("Company deleted.", "success")
        else:
            flash("Company not found.", "warning")
    except mysql.connector.Error as err:
        flash(f"Database error: {err.msg}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("companies"))

# MAIN

if __name__ == "__main__":
    app.run(debug=True)