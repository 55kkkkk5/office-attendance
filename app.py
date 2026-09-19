"""
Office Attendance System
-------------------------
QR-code based check-in/check-out with PIN confirmation, GPS location capture,
late-mark detection and an admin dashboard for owners.

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://<your-ip>:5000/checkin  (this is the link you turn into a QR code)
Admin dashboard: http://<your-ip>:5000/admin  (default password set below)
"""

import csv
import io
import os
import sqlite3
from datetime import datetime, date, time

from flask import (
    Flask, request, render_template, redirect, url_for,
    session, flash, send_file, g, jsonify
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")

# ---------------------------------------------------------------------------
# Configuration - change these for your office
# ---------------------------------------------------------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "office786")  # change this!
LATE_TIME = time(10, 15)     # after this time -> Late
OFFICE_CLOSE_TIME = time(19, 0)  # 7:00 PM
SUNDAY_IS_HOLIDAY = True

# Optional office geofence. Set OFFICE_LAT / OFFICE_LNG to your office's
# coordinates and OFFICE_RADIUS_M to how many meters away check-in is still
# allowed. Leave OFFICE_LAT as None to disable geofencing (location is still
# recorded, just not enforced).
OFFICE_LAT = None
OFFICE_LNG = None
OFFICE_RADIUS_M = 150

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-please")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'employee',   -- 'employee' or 'owner'
            pin TEXT NOT NULL DEFAULT '0000',
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            check_in_time TEXT,
            check_out_time TEXT,
            check_in_lat REAL,
            check_in_lng REAL,
            check_out_lat REAL,
            check_out_lng REAL,
            status TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, work_date)
        );
        """
    )
    db.commit()

    # Seed employees only if table is empty
    existing = db.execute("SELECT COUNT(*) c FROM employees").fetchone()[0]
    if existing == 0:
        owners = ["Hunain Khan", "Hammad Ahmed", "Fahad Ahmed"]
        employees = [
            "Arham Zafar", "Zaim", "Maaz", "Sinan", "Hassan Khan",
            "Abdullah", "Rehan", "Ahsan", "Huzaifa", "Hassan",
        ]
        for i, name in enumerate(owners):
            db.execute(
                "INSERT INTO employees (name, role, pin) VALUES (?, 'owner', ?)",
                (name, f"1{i:03d}"),
            )
        for i, name in enumerate(employees):
            db.execute(
                "INSERT INTO employees (name, role, pin) VALUES (?, 'employee', ?)",
                (name, f"2{i:03d}"),
            )
        db.commit()
        print("Seeded default employee list with starter PINs (see README).")
    db.close()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def compute_status(check_in_dt):
    """Return 'Present' or 'Late' based on check-in time."""
    if check_in_dt.time() > LATE_TIME:
        return "Late"
    return "Present"


def is_sunday(d: date) -> bool:
    return SUNDAY_IS_HOLIDAY and d.weekday() == 6  # Monday=0 ... Sunday=6


def haversine_m(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def require_admin():
    return session.get("is_admin", False)


# ---------------------------------------------------------------------------
# Employee-facing routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return redirect(url_for("checkin_page"))


@app.route("/checkin")
def checkin_page():
    db = get_db()
    employees = db.execute(
        "SELECT id, name, role FROM employees WHERE active = 1 ORDER BY role DESC, name"
    ).fetchall()
    return render_template(
        "checkin.html",
        employees=employees,
        late_time=LATE_TIME.strftime("%I:%M %p"),
        close_time=OFFICE_CLOSE_TIME.strftime("%I:%M %p"),
    )


@app.route("/api/mark", methods=["POST"])
def api_mark():
    """Called by the check-in page's JS after it gets GPS location."""
    data = request.get_json(force=True, silent=True) or {}
    employee_id = data.get("employee_id")
    pin = (data.get("pin") or "").strip()
    action = data.get("action")  # 'in' or 'out'
    lat = data.get("lat")
    lng = data.get("lng")

    if not employee_id or not pin or action not in ("in", "out"):
        return jsonify(ok=False, message="Missing information."), 400

    db = get_db()
    emp = db.execute(
        "SELECT * FROM employees WHERE id = ? AND active = 1", (employee_id,)
    ).fetchone()
    if not emp:
        return jsonify(ok=False, message="Employee not found."), 404
    if emp["pin"] != pin:
        return jsonify(ok=False, message="Galat PIN. Dobara try karein."), 403

    now = datetime.now()
    today = now.date()

    if is_sunday(today):
        return jsonify(ok=False, message="Aaj Sunday hai - office holiday."), 400

    if OFFICE_LAT is not None and lat is not None and lng is not None:
        dist = haversine_m(OFFICE_LAT, OFFICE_LNG, float(lat), float(lng))
        if dist > OFFICE_RADIUS_M:
            return jsonify(
                ok=False,
                message=f"Aap office se {int(dist)}m door hain. Office ke andar se scan karein.",
            ), 403

    row = db.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND work_date = ?",
        (employee_id, today.isoformat()),
    ).fetchone()

    if action == "in":
        if row and row["check_in_time"]:
            return jsonify(ok=False, message=f"{emp['name']} pehle hi check-in kar chuke hain aaj ({row['check_in_time']})."), 400
        status = compute_status(now)
        if row:
            db.execute(
                """UPDATE attendance SET check_in_time=?, check_in_lat=?, check_in_lng=?, status=?
                   WHERE id=?""",
                (now.strftime("%H:%M:%S"), lat, lng, status, row["id"]),
            )
        else:
            db.execute(
                """INSERT INTO attendance
                   (employee_id, work_date, check_in_time, check_in_lat, check_in_lng, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (employee_id, today.isoformat(), now.strftime("%H:%M:%S"), lat, lng, status),
            )
        db.commit()
        label = "Late" if status == "Late" else "Present"
        return jsonify(
            ok=True,
            message=f"Welcome, {emp['name']}! Check-in {now.strftime('%I:%M %p')} - {label}.",
        )

    else:  # check-out
        if not row or not row["check_in_time"]:
            return jsonify(ok=False, message="Pehle check-in karein."), 400
        if row["check_out_time"]:
            return jsonify(ok=False, message=f"{emp['name']} pehle hi check-out kar chuke hain ({row['check_out_time']})."), 400
        db.execute(
            "UPDATE attendance SET check_out_time=?, check_out_lat=?, check_out_lng=? WHERE id=?",
            (now.strftime("%H:%M:%S"), lat, lng, row["id"]),
        )
        db.commit()
        return jsonify(
            ok=True,
            message=f"Khuda Hafiz, {emp['name']}! Check-out {now.strftime('%I:%M %p')}.",
        )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Galat password.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_dashboard():
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    today = date.today().isoformat()
    rows = db.execute(
        """SELECT e.name, e.role, a.check_in_time, a.check_out_time, a.status
           FROM employees e
           LEFT JOIN attendance a ON a.employee_id = e.id AND a.work_date = ?
           WHERE e.active = 1
           ORDER BY e.role DESC, e.name""",
        (today,),
    ).fetchall()
    present = sum(1 for r in rows if r["check_in_time"])
    late = sum(1 for r in rows if r["status"] == "Late")
    total = len(rows)
    return render_template(
        "admin_dashboard.html",
        rows=rows, today=today, present=present, late=late, total=total,
        is_sunday=is_sunday(date.today()),
    )


@app.route("/admin/report")
def admin_report():
    if not require_admin():
        return redirect(url_for("admin_login"))
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    db = get_db()
    rows = db.execute(
        """SELECT e.name, e.role, a.work_date, a.check_in_time, a.check_out_time, a.status
           FROM attendance a JOIN employees e ON e.id = a.employee_id
           WHERE a.work_date LIKE ?
           ORDER BY a.work_date, e.name""",
        (month + "%",),
    ).fetchall()
    return render_template("admin_report.html", rows=rows, month=month)


@app.route("/admin/report.csv")
def admin_report_csv():
    if not require_admin():
        return redirect(url_for("admin_login"))
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    db = get_db()
    rows = db.execute(
        """SELECT e.name, e.role, a.work_date, a.check_in_time, a.check_out_time, a.status,
                  a.check_in_lat, a.check_in_lng
           FROM attendance a JOIN employees e ON e.id = a.employee_id
           WHERE a.work_date LIKE ?
           ORDER BY a.work_date, e.name""",
        (month + "%",),
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Role", "Date", "Check-in", "Check-out", "Status", "Lat", "Lng"])
    for r in rows:
        writer.writerow([r["name"], r["role"], r["work_date"], r["check_in_time"],
                          r["check_out_time"], r["status"], r["check_in_lat"], r["check_in_lng"]])
    mem = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True,
                      download_name=f"attendance_{month}.csv")


@app.route("/admin/employees", methods=["GET", "POST"])
def admin_employees():
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    if request.method == "POST":
        action = request.form.get("form_action")
        if action == "add":
            name = request.form.get("name", "").strip()
            role = request.form.get("role", "employee")
            pin = request.form.get("pin", "0000").strip()
            if name:
                try:
                    db.execute(
                        "INSERT INTO employees (name, role, pin) VALUES (?, ?, ?)",
                        (name, role, pin),
                    )
                    db.commit()
                    flash(f"{name} add ho gaye.")
                except sqlite3.IntegrityError:
                    flash("Yeh naam pehle se maujood hai.")
        elif action == "toggle":
            emp_id = request.form.get("emp_id")
            db.execute("UPDATE employees SET active = 1 - active WHERE id = ?", (emp_id,))
            db.commit()
        elif action == "pin":
            emp_id = request.form.get("emp_id")
            new_pin = request.form.get("new_pin", "").strip()
            if new_pin:
                db.execute("UPDATE employees SET pin = ? WHERE id = ?", (new_pin, emp_id))
                db.commit()
                flash("PIN update ho gaya.")
        return redirect(url_for("admin_employees"))

    employees = db.execute("SELECT * FROM employees ORDER BY role DESC, name").fetchall()
    return render_template("admin_employees.html", employees=employees)


# Make sure the database and tables exist whenever this module is imported -
# this runs both with `python app.py` AND with `gunicorn app:app` (Render,
# and most other hosts, start the app this second way, which skips the
# `if __name__ == "__main__"` block below).
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
