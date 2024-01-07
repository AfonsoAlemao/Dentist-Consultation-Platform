#!/usr/bin/python3
import os
from logging.config import dictConfig
import psycopg
from flask import flash
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from psycopg.rows import namedtuple_row
from datetime import datetime


# # postgres://{user}:{password}@{hostname}:{port}/{database-name}
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://db:db@postgres/db")

def validate_date(date):
    try:
        # Try to parse date using the correct format
        datetime.strptime(date, '%Y-%m-%d')
        return True  # date is valid
    except ValueError:
        return False  # date is invalid


dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
app.config.from_prefixed_env()
log = app.logger

app.secret_key = DATABASE_URL

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT VAT, Date, SUM (num_procedures) AS total_procedures, 
                    SUM (num_diagnostic_codes) AS total_diagnostic_codes
                FROM facts_consultations
                GROUP BY CUBE (VAT, Date);
            """)
            facts_consultations = cur.fetchall()
            app.logger.debug(f"Found {len(facts_consultations)} rows.")
    
    return render_template("dashboard/dashboard.html", facts_consultations=facts_consultations)

@app.route("/clients", methods=["GET"])
def clients():

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                ORDER BY name ASC;
            """)
            clients = cur.fetchall()
            app.logger.debug(f"Found {len(clients)} rows.")

    return render_template("clients/clients.html", clients=clients)

@app.route("/clients2", methods=["POST"])
def clients2():
    search = request.form.get("search")

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE name ILIKE %(search_like)s
                OR VAT = %(search)s
                OR street ILIKE %(search_like)s
                OR city ILIKE %(search_like)s
                OR zip ILIKE %(search_like)s
                ORDER BY name ASC;
            """, {'search': search, 'search_like': '%' + search + '%'})
            clients = cur.fetchall()
            app.logger.debug(f"Found {len(clients)} rows.")

    return render_template("clients/clients.html", clients=clients)

@app.route("/client/<VAT>", methods=["GET"])
def client_vat(VAT):

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT a.*, 
                    CASE WHEN c.VAT_doctor IS NOT NULL THEN TRUE ELSE FALSE END AS is_in_consultation
                FROM appointment AS a
                LEFT JOIN consultation AS c
                    ON a.VAT_doctor = c.VAT_doctor AND a.date_timestamp = c.date_timestamp
                WHERE a.VAT_client = %(VAT)s
                ORDER BY a.date_timestamp DESC;
            """, {"VAT": VAT})
            appointments = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} appointment(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s
                ORDER BY c.date_timestamp;
            """, {"VAT": VAT})
            consultations = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            

    return render_template("clients/client_vat.html", client = client, consultations = consultations, appointments = appointments)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>", methods=["GET"])
def consultation_desc(VAT, VAT_doctor, date_timestamp):

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT *
                FROM appointment
                WHERE VAT_client = %(VAT)s AND VAT_doctor = %(VAT_doctor)s AND date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            appointment = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} appointment(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            
            cur.execute("""
                SELECT pc.name, pc.VAT_doctor, pc.date_timestamp, pc.description
                FROM procedure_in_consultation AS pc
                JOIN consultation AS c ON c.VAT_doctor = pc.VAT_doctor AND c.date_timestamp = pc.date_timestamp
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s
                ORDER BY pc.date_timestamp;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            procedures = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} procedure(s).")
            
            cur.execute("""
                SELECT dc.ID, dc.description
                FROM diagnostic_code AS dc
                JOIN consultation_diagnostic AS cd ON cd.ID = dc.ID
                JOIN consultation AS c ON c.VAT_doctor = cd.VAT_doctor AND c.date_timestamp = cd.date_timestamp
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s
                ORDER BY cd.date_timestamp;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            diagnosis = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} diagnosi(s).")
            
            
            cur.execute("""
                SELECT n.VAT, e.name
                FROM nurse AS n
                JOIN employee AS e ON e.VAT = n.VAT
                JOIN consultation_assistant AS ca ON ca.VAT_nurse = n.VAT
                JOIN consultation AS c ON c.VAT_doctor = ca.VAT_doctor AND c.date_timestamp = ca.date_timestamp
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            nurses = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} nurse(s).")

    return render_template("clients/consultation_desc.html", client = client, consultation = consultation, appointment = appointment, procedures = procedures, diagnosis = diagnosis, nurses = nurses)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_consultation", methods=["POST"])
def update_consultation_dashboard(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            
    return render_template("clients/update_consultation.html", consultation = consultation, client = client)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_consultation2", methods=["POST"])
def update_consultation(VAT, VAT_doctor, date_timestamp):
    soap_s = request.form.get("soap_s")
    soap_o = request.form.get("soap_o")
    soap_a = request.form.get("soap_a")
    soap_p = request.form.get("soap_p")
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/update_consultation')

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                UPDATE consultation
                SET SOAP_S = %(soap_s)s, SOAP_O = %(soap_o)s, SOAP_A = %(soap_a)s, SOAP_P = %(soap_p)s
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "soap_s": soap_s, "soap_o": soap_o, "soap_a": soap_a, "soap_p": soap_p})
        
            conn.commit()

    flash('Consultation updated successfully.')
    
    
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_appointment", methods=["POST"])
def update_appointment_dashboard(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM appointment
                WHERE VAT_client = %(VAT)s AND VAT_doctor = %(VAT_doctor)s AND date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            appointment = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} appointment(s).")
            
            cur.execute("""
                    SELECT *
                    FROM client
                    WHERE VAT = %(VAT)s;
                """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            
    return render_template("clients/update_appointment.html", appointment = appointment, client = client)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_appointment2", methods=["POST"])
def update_appointment(VAT, VAT_doctor, date_timestamp):
    description = request.form.get("description")
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/update_appointment')

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                UPDATE appointment
                SET description = %(description)s
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "description": description})
            
            conn.commit()

    flash('Appointment updated successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_procedure/<name>", methods=["POST"])
def update_procedure_dashboard(VAT, VAT_doctor, date_timestamp, name):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT pc.name, pc.VAT_doctor, pc.date_timestamp, pc.description
                FROM procedure_in_consultation AS pc
                JOIN consultation AS c ON c.VAT_doctor = pc.VAT_doctor AND c.date_timestamp = pc.date_timestamp
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s 
                    AND pc.name = %(name)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "name": name})
            procedure = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} procedure(s).")
            
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            
    return render_template("clients/update_procedure.html", procedure = procedure, client = client)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/update_procedure2/<name>", methods=["POST"])
def update_procedure(VAT, VAT_doctor, date_timestamp, name):
    description = request.form.get("description")
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/update_procedure' + '/' + name)

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                UPDATE procedure_in_consultation
                SET description = %(description)s
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND name = %(name)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "description": description, "name": name})
            
            conn.commit()

    flash('Procedure updated successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)


@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/delete_procedure/<name>", methods=["POST"])
def delete_procedure(VAT, VAT_doctor, date_timestamp, name):
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                DELETE FROM procedure_charting
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND name = %(name)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "name": name})
            
            cur.execute("""
                DELETE FROM procedure_imaging
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND name = %(name)s;
                
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "name": name})
            
            cur.execute("""
                DELETE FROM procedure_in_consultation
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND name = %(name)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "name": name})
            
            conn.commit()

    flash('Procedure deleted successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/delete_nurse/<VAT_nurse>", methods=["POST"])
def delete_nurse(VAT, VAT_doctor, date_timestamp, VAT_nurse):
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                DELETE FROM consultation_assistant
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND VAT_nurse = %(VAT_nurse)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "VAT_nurse": VAT_nurse})
            
            conn.commit()

    flash('Nurse deleted successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/delete_diagnostic/<ID>", methods=["POST"])
def delete_diagnostic(VAT, VAT_doctor, date_timestamp, ID):
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                DELETE FROM prescription
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND ID = %(ID)s;        
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "ID": ID})
            
            cur.execute("""
                DELETE FROM consultation_diagnostic
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s AND ID = %(ID)s;
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "ID": ID})
            
            conn.commit()

    flash('Diagnostic deleted successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_procedure2", methods=["POST"])
def add_procedure(VAT, VAT_doctor, date_timestamp):
    description = request.form.get("description")
    
    error = ""
    
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT name
                FROM procedure;
                """)
            db_procedures = cur.fetchall()
            db_procedures = [row.name for row in db_procedures]
            app.logger.debug(f"Found {cur.rowcount} db_procedure(s).")
            
            cur.execute("""
                SELECT name
                FROM procedure_in_consultation
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s;
                """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            db_names = cur.fetchall()
            db_names = [row.name for row in db_names]
            app.logger.debug(f"Found {cur.rowcount} db_procedure(s).")
    
    name = request.form.get("name")
    
    if name not in(db_procedures) or name in(db_names):
        error = "Invalid procedure name"

    if error != "":
        flash(error)
        return redirect('/client/' + VAT + '/' + VAT_doctor  + '/' + date_timestamp + '/add_procedure')


    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                INSERT INTO procedure_in_consultation (name, VAT_doctor, date_timestamp, description)
                VALUES
                (%(name)s, %(VAT_doctor)s, %(date_timestamp)s, %(description)s);
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "name": name, "description": description})
            
            conn.commit()

    flash('Procedure created successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_nurse2", methods=["POST"])
def add_nurse(VAT, VAT_doctor, date_timestamp):
    
    error = ""
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT VAT
                FROM nurse;
                """)
            db_VAT_nurses = cur.fetchall()
            db_VAT_nurses = [row.vat for row in db_VAT_nurses]
            app.logger.debug(f"Found {cur.rowcount} db_VAT_nurses.")
    
    VAT_nurse = request.form.get("VAT")
    
    if VAT_nurse not in(db_VAT_nurses):
        error = "Invalid VAT_nurse"

    if error != "":
        flash(error)
        
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/add_nurse')

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                INSERT INTO consultation_assistant(VAT_doctor, date_timestamp, VAT_nurse)
                VALUES
                (%(VAT_doctor)s, %(date_timestamp)s, %(VAT_nurse)s);
            
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "VAT_nurse": VAT_nurse})
            
            conn.commit()

    flash('Nurse created successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_diagnostic2", methods=["POST"])
def add_diagnostic2(VAT, VAT_doctor, date_timestamp):
    
    error = ""
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT ID
                FROM diagnostic_code;
                """)
            db_ID = cur.fetchall()
            db_ID = [row.id for row in db_ID]
            app.logger.debug(f"Found {cur.rowcount} db_ID(s).")
            
            cur.execute("""
                SELECT ID
                FROM consultation_diagnostic
                WHERE date_timestamp = %(date_timestamp)s AND VAT_doctor = %(VAT_doctor)s;               ;
                """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            db_ID2 = cur.fetchall()
            db_ID2 = [row.id for row in db_ID2]
            app.logger.debug(f"Found {cur.rowcount} db_ID2(s).")
            
    ID = request.form.get("ID")
    
    if ID not in(db_ID) or ID in(db_ID2):
        error = "Invalid ID"

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/add_diagnostic')

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                INSERT INTO consultation_diagnostic (VAT_doctor, date_timestamp, ID)
                VALUES
                (%(VAT_doctor)s, %(date_timestamp)s, %(ID)s);
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "ID": ID})
            
            conn.commit()

    flash('Diagnostic created successfully.')
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_procedure", methods=["GET"])
def add_procedure_dashboard(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            cur.execute("""
                SELECT name
                FROM procedure_in_consultation;
                """)
            db_procedures = cur.fetchall()
            db_procedures = [row.name for row in db_procedures]
            app.logger.debug(f"Found {cur.rowcount} db_procedure(s).")
            
    
    return render_template("clients/add_procedure.html", client = client, consultation = consultation, procedures_names = db_procedures)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_nurse", methods=["GET"])
def add_nurse_dashboard(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            cur.execute("""
                SELECT VAT
                FROM nurse;
                """)
            db_VAT_nurses = cur.fetchall()
            db_VAT_nurses = [row.vat for row in db_VAT_nurses]
            app.logger.debug(f"Found {cur.rowcount} db_VAT_nurses.")
                    
            
    return render_template("clients/add_nurse.html", client = client, consultation = consultation, VAT_nurses = db_VAT_nurses)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/add_diagnostic", methods=["GET"])
def add_diagnostic(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            cur.execute("""
                SELECT ID
                FROM diagnostic_code;
                """)
            db_ID = cur.fetchall()
            db_ID = [row.id for row in db_ID]
            app.logger.debug(f"Found {cur.rowcount} db_ID(s).")
            
            
    return render_template("clients/add_diagnostic.html", client = client, consultation = consultation, IDs = db_ID)

@app.route("/client/<VAT>/new_appointment", methods=["GET"])
def add_appointment_dashboard(VAT):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT *
                FROM appointment;
            """)
            appointments = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} appointment(s).")      
                     
    available_slots = ['9:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    return render_template("clients/add_appointment.html", client = client, appointments = appointments, available_slots = available_slots)

@app.route("/client/<VAT>/new_appointment_doctor", methods=["POST"])
def add_appointment_doctor_dashboard(VAT):
    date = request.form.get("date")
    time = request.form.get("time") + ":00"
    datetime_str = date + " " + time
    format_str = "%Y-%m-%d %H:%M:%S"
    datetime_obj = datetime.strptime(datetime_str, format_str)
    date_timestamp = datetime.timestamp(datetime_obj)
    date_timestamp = datetime_obj.strftime(format_str)

    
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
                
            
            cur.execute("""
                SELECT e.name, d.specialization, d.email, d.biography, e.VAT
                FROM doctor AS d JOIN employee as e ON e.VAT = d.VAT
                WHERE d.VAT NOT IN(
                    SELECT d1.VAT 
                    FROM doctor AS d1
                    JOIN appointment AS a ON a.VAT_doctor = d1.VAT
                    WHERE a.date_timestamp = %(date_timestamp)s
                )
                ORDER BY e.VAT;
            """, {"date_timestamp": date_timestamp})
            doctors = cur.fetchall()
            app.logger.debug(f"Found {cur.rowcount} doctor(s).")           
            
    return render_template("clients/add_appointment_doctor.html", client = client, doctors = doctors, date_timestamp = date_timestamp)

@app.route("/client/<VAT>/<date_timestamp>/new_appointment2", methods=["POST"])
def add_appointment2(VAT, date_timestamp):
    VAT_doctor = request.form.get("VAT_doctor")
    description = request.form.get("description")
    error = ""

    if error != "":
        flash(error)
        
        return redirect('/client/' + VAT)

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                        
                INSERT INTO appointment (VAT_doctor, date_timestamp, VAT_client, description)
                VALUES
                (%(VAT_doctor)s, %(date_timestamp)s, %(VAT_client)s, %(description)s);
                
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "description": description, "VAT_client": VAT})
            
            conn.commit()

    flash('Appointment created successfully.')
    return redirect('/client/' + VAT)

@app.route("/new_client", methods=["GET"])
def add_client_dashboard():

    return render_template("clients/new_client.html")

@app.route("/new_client2", methods=["POST"])
def add_client2():
    VAT = request.form.get("vat")
    name = request.form.get("name")
    birth_date = request.form.get("birth_date")
    street = request.form.get("street")
    city = request.form.get("city")
    gender = request.form.get("gender")
    zip_code = request.form.get("zip")
    
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT VAT
                FROM client;
                """)
            
            db_VAT_client = cur.fetchall()
            db_VAT_client = [row.vat for row in db_VAT_client]
            app.logger.debug(f"Found {cur.rowcount} db_VAT_client(s).")
    
    error = ""
        
    if VAT in db_VAT_client:
        error = 'VAT client already exists'
        
    if not validate_date(birth_date):
        error = "birthdate is invalid"
        
    if error != "":
        flash(error)
        return render_template("clients/new_client.html")

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                INSERT INTO client(VAT, name, birth_date, street, city, zip, gender)
                VALUES
                (%(VAT)s, %(name)s, %(birth_date)s, %(street)s, %(city)s, %(zip)s, %(gender)s);
            
            """, {"VAT": VAT, "name": name, "birth_date": birth_date, "street": street, 
                  "city": city, "zip": zip_code, "gender": gender})
            
            conn.commit()

    flash('Client created successfully.')
    return redirect('/dashboard')

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/create_consultation", methods=["GET"])
def add_consultation_dashboard(VAT, VAT_doctor, date_timestamp):
    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                SELECT *
                FROM client
                WHERE VAT = %(VAT)s;
            """, {"VAT": VAT})
            client = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} client(s).")
            
            cur.execute("""
                SELECT c.VAT_doctor,  c.date_timestamp, c.soap_s, c.soap_o, c.soap_a, c.soap_p
                FROM consultation AS c
                JOIN appointment AS a ON c.VAT_doctor = a.VAT_doctor AND c.date_timestamp = a.date_timestamp
                WHERE a.VAT_client = %(VAT)s AND a.VAT_doctor = %(VAT_doctor)s AND a.date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            consultation = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} consultation(s).")
            
            cur.execute("""
                SELECT *
                FROM appointment
                WHERE VAT_client = %(VAT)s AND VAT_doctor = %(VAT_doctor)s AND date_timestamp = %(date_timestamp)s;
            """, {"VAT": VAT, "VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp})
            appointment = cur.fetchone()
            app.logger.debug(f"Found {cur.rowcount} appointment(s).")
            
    return render_template("clients/create_consultation.html", client = client, consultation = consultation, appointment = appointment)

@app.route("/client/<VAT>/<VAT_doctor>/<date_timestamp>/create_consultation2", methods=["POST"])
def add_consultation2(VAT, VAT_doctor, date_timestamp):
    soap_s = request.form.get("soap_s")
    soap_o = request.form.get("soap_o")
    soap_a = request.form.get("soap_a")
    soap_p = request.form.get("soap_p")
    
    error = ""

    if error != "":
        flash(error)
        return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp + '/update_consultation')

    with psycopg.connect(conninfo=DATABASE_URL) as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("""
                INSERT INTO consultation (VAT_doctor, date_timestamp, SOAP_S, SOAP_O, SOAP_A, SOAP_P)
                VALUES
                (%(VAT_doctor)s, %(date_timestamp)s, %(soap_s)s, %(soap_o)s, %(soap_a)s, %(soap_p)s);
            """, {"VAT_doctor": VAT_doctor, "date_timestamp": date_timestamp, "soap_s": soap_s, "soap_o": soap_o, "soap_a": soap_a, "soap_p": soap_p})
        
            conn.commit()

    flash('Consultation created successfully.')
    
    
    return redirect('/' + 'client' + '/' + VAT + '/' + VAT_doctor + '/' + date_timestamp)

if __name__ == "__main__":
    app.run()