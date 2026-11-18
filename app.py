import os
import json
import re
from datetime import datetime
import mysql.connector
from flask import Flask, render_template, redirect, url_for, request, flash
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# DASHBOARD SECTION

# Redirect home page to dashboard
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


# Show dashboard stats and recent applications
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
# Clean form input
def clean(value):
    value = (value or "").strip()
    return value or None

# Get all rows from a query
def query_all(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


# Get one row from a query
def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


# Run insert, update or delete queries
def run_write(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    except mysql.connector.Error as err:
        flash(f"Database error: {err.msg}", "danger")
        return None
    finally:
        cursor.close()
        conn.close()


# Show validation errors
def flash_errors(errors):
    for error in errors:
        flash(error, "danger")


# Convert JSON column to Python data
def parse_json(value, default):
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value


# Check if a date is valid
def valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# Format numbers as money
@app.template_filter("money")
def money(value):
    return f"${value:,}" if value is not None else "—"

# COMPANY SECTION

COMPANY_FIELDS = ["company_name", "industry", "website", "city", "state", "notes"]


# Read and validate company form
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


# Render companies page
def render_companies_page(form=None, edit_id=None):
    companies = query_all("SELECT * FROM companies ORDER BY company_name")
    return render_template("companies.html", companies=companies,
                           form=form or {}, edit_id=edit_id, detail=None)


# Show companies list
@app.route("/companies")
def companies():
    return render_companies_page()


# Show company details
@app.route("/companies/<int:company_id>")
def company_detail(company_id):
    company = query_one("SELECT * FROM companies WHERE company_id = %s", (company_id,))
    if company is None:
        flash("Company not found.", "warning")
        return redirect(url_for("companies"))
    jobs = query_all("SELECT job_id, job_title, job_type FROM jobs WHERE company_id = %s",
                     (company_id,))
    contacts = query_all("""
        SELECT contact_id, contact_name, title, email
        FROM contacts WHERE company_id = %s
    """, (company_id,))
    return render_template("companies.html", detail=company, jobs=jobs, contacts=contacts)


# Add a company
@app.route("/companies/add", methods=["POST"])
def add_company():
    data, errors = get_company_form()
    if errors:
        flash_errors(errors)
        return render_companies_page(form=data)

    result = run_write("""
        INSERT INTO companies (company_name, industry, website, city, state, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [data[f] for f in COMPANY_FIELDS])
    if result is not None:
        flash(f"Company '{data['company_name']}' added.", "success")
    return redirect(url_for("companies"))


# Edit a company
@app.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
def edit_company(company_id):
    if request.method == "POST":
        data, errors = get_company_form()
        if errors:
            flash_errors(errors)
            return render_companies_page(form=data, edit_id=company_id)

        result = run_write("""
            UPDATE companies
            SET company_name = %s, industry = %s, website = %s,
                city = %s, state = %s, notes = %s
            WHERE company_id = %s
        """, [data[f] for f in COMPANY_FIELDS] + [company_id])
        if result is not None:
            flash(f"Company '{data['company_name']}' updated.", "success")
        return redirect(url_for("companies"))

    company = query_one("SELECT * FROM companies WHERE company_id = %s", (company_id,))
    if company is None:
        flash("Company not found.", "warning")
        return redirect(url_for("companies"))
    return render_companies_page(form=company, edit_id=company_id)


# Delete a company
@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id):
    result = run_write("DELETE FROM companies WHERE company_id = %s", (company_id,))
    if result:
        flash("Company deleted.", "success")
    elif result == 0:
        flash("Company not found.", "warning")
    return redirect(url_for("companies"))

# JOBS SECTION

JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]


# Read and validate job form
def get_job_form():
    data = {field: clean(request.form.get(field)) for field in
            ["company_id", "job_title", "job_type", "salary_min",
             "salary_max", "job_url", "date_posted", "requirements"]}
    errors = []

    if not (data["company_id"] and data["company_id"].isdigit()
            and query_one("SELECT company_id FROM companies WHERE company_id = %s",
                          (data["company_id"],))):
        errors.append("Please select a valid company.")

    if not data["job_title"]:
        errors.append("Job title is required.")
    elif len(data["job_title"]) > 100:
        errors.append("Job title must be 100 characters or fewer.")

    if data["job_type"] and data["job_type"] not in JOB_TYPES:
        errors.append("Invalid job type.")

    for field in ("salary_min", "salary_max"):
        if data[field] and not data[field].isdigit():
            errors.append(f"{field.replace('_', ' ').capitalize()} must be a whole positive number.")
    if (data["salary_min"] and data["salary_max"]
            and data["salary_min"].isdigit() and data["salary_max"].isdigit()
            and int(data["salary_min"]) > int(data["salary_max"])):
        errors.append("Minimum salary cannot be greater than maximum salary.")

    if data["job_url"]:
        if len(data["job_url"]) > 300:
            errors.append("Job URL must be 300 characters or fewer.")
        elif not data["job_url"].startswith(("http://", "https://")):
            errors.append("Job URL must start with http:// or https://")

    if data["date_posted"] and not valid_date(data["date_posted"]):
        errors.append("Date posted must be a valid date.")

    skills = []
    for skill in (data["requirements"] or "").split(","):
        skill = skill.strip()
        if skill and skill.lower() not in [s.lower() for s in skills]:
            skills.append(skill)

    return data, skills, errors


# Prepare job values for the database
def job_values(data, skills):
    return [
        int(data["company_id"]),
        data["job_title"],
        data["job_type"],
        int(data["salary_min"]) if data["salary_min"] else None,
        int(data["salary_max"]) if data["salary_max"] else None,
        data["job_url"],
        data["date_posted"],
        json.dumps(skills) if skills else None,
    ]


# Render jobs page
def render_jobs_page(form=None, edit_id=None):
    jobs = query_all("""
        SELECT j.*, c.company_name
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.company_id
        ORDER BY j.date_posted DESC
    """)
    for job in jobs:
        job["skills"] = parse_json(job["requirements"], [])
    companies = query_all("SELECT company_id, company_name FROM companies ORDER BY company_name")
    return render_template("jobs.html", jobs=jobs, companies=companies,
                           job_types=JOB_TYPES, form=form or {},
                           edit_id=edit_id, detail=None)


# Show jobs list
@app.route("/jobs")
def jobs():
    return render_jobs_page()


# Show job details
@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = query_one("""
        SELECT j.*, c.company_name
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.company_id
        WHERE j.job_id = %s
    """, (job_id,))
    if job is None:
        flash("Job not found.", "warning")
        return redirect(url_for("jobs"))
    job["skills"] = parse_json(job["requirements"], [])
    applications = query_all("""
        SELECT application_id, application_date, status
        FROM applications WHERE job_id = %s
        ORDER BY application_date DESC
    """, (job_id,))
    return render_template("jobs.html", detail=job, applications=applications)


# Add a job
@app.route("/jobs/add", methods=["POST"])
def add_job():
    data, skills, errors = get_job_form()
    if errors:
        flash_errors(errors)
        return render_jobs_page(form=data)

    result = run_write("""
        INSERT INTO jobs (company_id, job_title, job_type, salary_min,
                          salary_max, job_url, date_posted, requirements)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, job_values(data, skills))
    if result is not None:
        flash(f"Job '{data['job_title']}' added.", "success")
    return redirect(url_for("jobs"))


# Edit a job
@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    if request.method == "POST":
        data, skills, errors = get_job_form()
        if errors:
            flash_errors(errors)
            return render_jobs_page(form=data, edit_id=job_id)

        result = run_write("""
            UPDATE jobs
            SET company_id = %s, job_title = %s, job_type = %s, salary_min = %s,
                salary_max = %s, job_url = %s, date_posted = %s, requirements = %s
            WHERE job_id = %s
        """, job_values(data, skills) + [job_id])
        if result is not None:
            flash(f"Job '{data['job_title']}' updated.", "success")
        return redirect(url_for("jobs"))

    job = query_one("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
    if job is None:
        flash("Job not found.", "warning")
        return redirect(url_for("jobs"))
    job["requirements"] = ", ".join(parse_json(job["requirements"], []))
    return render_jobs_page(form=job, edit_id=job_id)


# Delete a job
@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    result = run_write("DELETE FROM jobs WHERE job_id = %s", (job_id,))
    if result:
        flash("Job deleted.", "success")
    elif result == 0:
        flash("Job not found.", "warning")
    return redirect(url_for("jobs"))

# APPLICATION SECTION

APP_STATUSES = ["Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]


# Read and validate application form
def get_application_form():
    data = {field: clean(request.form.get(field)) for field in
            ["job_id", "application_date", "status", "resume_version",
             "interview_round", "interviewer", "interview_notes"]}
    data["cover_letter_sent"] = "cover_letter_sent" in request.form
    errors = []

    if not (data["job_id"] and data["job_id"].isdigit()
            and query_one("SELECT job_id FROM jobs WHERE job_id = %s", (data["job_id"],))):
        errors.append("Please select a valid job.")

    if not data["application_date"]:
        errors.append("Application date is required.")
    elif not valid_date(data["application_date"]):
        errors.append("Application date must be a valid date.")

    if data["status"] not in APP_STATUSES:
        errors.append("Please select a valid status.")

    if data["resume_version"] and len(data["resume_version"]) > 50:
        errors.append("Resume version must be 50 characters or fewer.")

    if data["interview_round"] and not data["interview_round"].isdigit():
        errors.append("Interview round must be a whole number.")

    # Build the interview_data JSON object from the optional fields
    interview = {}
    if data["interview_round"] and data["interview_round"].isdigit():
        interview["round"] = int(data["interview_round"])
    if data["interviewer"]:
        interview["interviewer"] = data["interviewer"]
    if data["interview_notes"]:
        interview["notes"] = data["interview_notes"]

    return data, interview, errors


# Prepare application values for the database
def application_values(data, interview):
    return [
        int(data["job_id"]),
        data["application_date"],
        data["status"],
        data["resume_version"],
        data["cover_letter_sent"],
        json.dumps(interview) if interview else None,
    ]


# Render applications page
def render_applications_page(form=None, edit_id=None):
    applications = query_all("""
        SELECT a.*, j.job_title, c.company_name
        FROM applications a
        LEFT JOIN jobs j ON a.job_id = j.job_id
        LEFT JOIN companies c ON j.company_id = c.company_id
        ORDER BY a.application_date DESC
    """)
    jobs = query_all("""
        SELECT j.job_id, j.job_title, c.company_name
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.company_id
        ORDER BY c.company_name, j.job_title
    """)
    if form is None:
        form = {"status": "Applied", "application_date": datetime.today().strftime("%Y-%m-%d")}
    return render_template("applications.html", applications=applications, jobs=jobs,
                           statuses=APP_STATUSES, form=form, edit_id=edit_id, detail=None)


# Show applications list
@app.route("/applications")
def applications():
    return render_applications_page()


# Show application details
@app.route("/applications/<int:application_id>")
def application_detail(application_id):
    application = query_one("""
        SELECT a.*, j.job_title, c.company_id, c.company_name
        FROM applications a
        LEFT JOIN jobs j ON a.job_id = j.job_id
        LEFT JOIN companies c ON j.company_id = c.company_id
        WHERE a.application_id = %s
    """, (application_id,))
    if application is None:
        flash("Application not found.", "warning")
        return redirect(url_for("applications"))
    application["interview"] = parse_json(application["interview_data"], {})
    return render_template("applications.html", detail=application)


# Add an application
@app.route("/applications/add", methods=["POST"])
def add_application():
    data, interview, errors = get_application_form()
    if errors:
        flash_errors(errors)
        return render_applications_page(form=data)

    result = run_write("""
        INSERT INTO applications (job_id, application_date, status,
                                  resume_version, cover_letter_sent, interview_data)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, application_values(data, interview))
    if result is not None:
        flash("Application added.", "success")
    return redirect(url_for("applications"))


# Edit an application
@app.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
def edit_application(application_id):
    if request.method == "POST":
        data, interview, errors = get_application_form()
        if errors:
            flash_errors(errors)
            return render_applications_page(form=data, edit_id=application_id)

        result = run_write("""
            UPDATE applications
            SET job_id = %s, application_date = %s, status = %s,
                resume_version = %s, cover_letter_sent = %s, interview_data = %s
            WHERE application_id = %s
        """, application_values(data, interview) + [application_id])
        if result is not None:
            flash("Application updated.", "success")
        return redirect(url_for("applications"))

    application = query_one("SELECT * FROM applications WHERE application_id = %s",
                            (application_id,))
    if application is None:
        flash("Application not found.", "warning")
        return redirect(url_for("applications"))
    interview = parse_json(application["interview_data"], {})
    application["interview_round"] = interview.get("round")
    application["interviewer"] = interview.get("interviewer")
    application["interview_notes"] = interview.get("notes")
    return render_applications_page(form=application, edit_id=application_id)


# Delete an application
@app.route("/applications/<int:application_id>/delete", methods=["POST"])
def delete_application(application_id):
    result = run_write("DELETE FROM applications WHERE application_id = %s", (application_id,))
    if result:
        flash("Application deleted.", "success")
    elif result == 0:
        flash("Application not found.", "warning")
    return redirect(url_for("applications"))

# CONTACTS SECTION

CONTACT_FIELDS = ["company_id", "contact_name", "title", "email",
                  "phone", "linkedin_url", "notes"]
EMAIL_PATTERN = r"[^@\s]+@[^@\s]+\.[^@\s]+"
PHONE_PATTERN = r"[0-9\s\-\(\)\+\.]{7,20}"


# Read and validate contact form
def get_contact_form():
    data = {field: clean(request.form.get(field)) for field in CONTACT_FIELDS}
    errors = []

    if not (data["company_id"] and data["company_id"].isdigit()
            and query_one("SELECT company_id FROM companies WHERE company_id = %s",
                          (data["company_id"],))):
        errors.append("Please select a valid company.")

    if not data["contact_name"]:
        errors.append("Contact name is required.")

    limits = {"contact_name": 100, "title": 100, "email": 100,
              "phone": 20, "linkedin_url": 200}
    for field, limit in limits.items():
        if data[field] and len(data[field]) > limit:
            label = field.replace("_", " ").capitalize()
            errors.append(f"{label} must be {limit} characters or fewer.")

    if data["email"] and not re.fullmatch(EMAIL_PATTERN, data["email"]):
        errors.append("Email address is not valid.")

    if data["phone"] and not re.fullmatch(PHONE_PATTERN, data["phone"]):
        errors.append("Phone may only contain digits, spaces and + - ( ) . (7-20 characters).")

    if data["linkedin_url"] and not data["linkedin_url"].startswith(("http://", "https://")):
        errors.append("LinkedIn URL must start with http:// or https://")

    return data, errors


# Prepare contact values for the database
def contact_values(data):
    values = [data[f] for f in CONTACT_FIELDS]
    values[0] = int(values[0])
    return values


# Render contacts page
def render_contacts_page(form=None, edit_id=None):
    contacts = query_all("""
        SELECT ct.*, c.company_name
        FROM contacts ct
        LEFT JOIN companies c ON ct.company_id = c.company_id
        ORDER BY ct.contact_name
    """)
    companies = query_all("SELECT company_id, company_name FROM companies ORDER BY company_name")
    return render_template("contacts.html", contacts=contacts, companies=companies,
                           form=form or {}, edit_id=edit_id, detail=None)


# Show contacts list
@app.route("/contacts")
def contacts():
    return render_contacts_page()


# Show contact details
@app.route("/contacts/<int:contact_id>")
def contact_detail(contact_id):
    contact = query_one("""
        SELECT ct.*, c.company_name
        FROM contacts ct
        LEFT JOIN companies c ON ct.company_id = c.company_id
        WHERE ct.contact_id = %s
    """, (contact_id,))
    if contact is None:
        flash("Contact not found.", "warning")
        return redirect(url_for("contacts"))
    return render_template("contacts.html", detail=contact)


# Add a contact
@app.route("/contacts/add", methods=["POST"])
def add_contact():
    data, errors = get_contact_form()
    if errors:
        flash_errors(errors)
        return render_contacts_page(form=data)

    result = run_write("""
        INSERT INTO contacts (company_id, contact_name, title, email,
                              phone, linkedin_url, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, contact_values(data))
    if result is not None:
        flash(f"Contact '{data['contact_name']}' added.", "success")
    return redirect(url_for("contacts"))


# Edit a contact
@app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
def edit_contact(contact_id):
    if request.method == "POST":
        data, errors = get_contact_form()
        if errors:
            flash_errors(errors)
            return render_contacts_page(form=data, edit_id=contact_id)

        result = run_write("""
            UPDATE contacts
            SET company_id = %s, contact_name = %s, title = %s, email = %s,
                phone = %s, linkedin_url = %s, notes = %s
            WHERE contact_id = %s
        """, contact_values(data) + [contact_id])
        if result is not None:
            flash(f"Contact '{data['contact_name']}' updated.", "success")
        return redirect(url_for("contacts"))

    contact = query_one("SELECT * FROM contacts WHERE contact_id = %s", (contact_id,))
    if contact is None:
        flash("Contact not found.", "warning")
        return redirect(url_for("contacts"))
    return render_contacts_page(form=contact, edit_id=contact_id)


# Delete a contact
@app.route("/contacts/<int:contact_id>/delete", methods=["POST"])
def delete_contact(contact_id):
    result = run_write("DELETE FROM contacts WHERE contact_id = %s", (contact_id,))
    if result:
        flash("Contact deleted.", "success")
    elif result == 0:
        flash("Contact not found.", "warning")
    return redirect(url_for("contacts"))

# JOB MATCH

# Rank jobs by skill match
@app.route("/job-match")
def job_match():
    raw = request.args.get("skills", "")
    user_skills = [s.strip() for s in raw.split(",") if s.strip()]
    user_set = {s.lower() for s in user_skills}

    jobs = query_all("""
        SELECT j.job_id, j.job_title, j.requirements, c.company_name
        FROM jobs j
        LEFT JOIN companies c ON j.company_id = c.company_id
    """)

    all_skills = set()
    results = []
    for job in jobs:
        required = parse_json(job["requirements"], [])
        all_skills.update(required)
        if not required or not user_set:
            continue

        matched = [s for s in required if s.lower() in user_set]
        missing = [s for s in required if s.lower() not in user_set]
        if not matched:
            continue

        results.append({
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "company_name": job["company_name"],
            "matched": matched,
            "missing": missing,
            "total": len(required),
            "percent": round(len(matched) / len(required) * 100),
        })

    results.sort(key=lambda r: (r["percent"], len(r["matched"])), reverse=True)

    return render_template("job_match.html", skills=raw, results=results,
                           searched=bool(user_set),
                           all_skills=sorted(all_skills, key=str.lower))

# MAIN

if __name__ == "__main__":
    app.run(debug=True)