from flask import Flask, render_template, request, redirect, session, flash, url_for, send_from_directory
import sqlite3, os, hashlib, uuid
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= PASSWORD HASH =================
def hash_password(password):
    return hashlib.sha256((password + "secure_salt").encode()).hexdigest()

# ================= DB INIT =================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        ip TEXT,
        time TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        filename TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= IP + LOCATION =================
def get_real_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def get_location(ip):
    try:
        data = requests.get(f"http://ip-api.com/json/{ip}").json()
        return data.get("city", "Unknown")
    except:
        return "Unknown"

# ================= HOME =================
@app.route("/")
def home():
    return redirect("/login")

# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = hash_password(request.form.get("password"))

        ip = get_real_ip()
        city = get_location(ip)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()

        if user and user[2] == password:
            session["user"] = username

            c.execute("INSERT INTO logs(username,ip,time) VALUES(?,?,?)",
                      (username, f"{ip} ({city})", str(datetime.now())))

            conn.commit()
            conn.close()

            return redirect("/dashboard")
        else:
            flash("login_error")

        conn.close()

    return render_template("login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            flash("password_mismatch")
            return redirect("/register")

        password = hash_password(password)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(username,password))
            conn.commit()
            flash("account_created")
            return redirect("/login")
        except:
            flash("user_exists")

        conn.close()

    return render_template("register.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    files_data = []
    for file in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, file)
        timestamp = os.path.getmtime(filepath)

        files_data.append({
            "name": file,
            "time": datetime.fromtimestamp(timestamp).strftime("%d-%m-%Y %I:%M %p")
        })

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT ip,time FROM logs WHERE username=?", (session["user"],))
    logs = c.fetchall()
    conn.close()

    file_count = len(files_data)

    return render_template("dashboard.html",
                           files=files_data,
                           logs=logs,
                           file_count=file_count)

@app.route("/uploads")
def uploads_page():
    if "user" not in session:
        return redirect("/login")

    files = os.listdir(UPLOAD_FOLDER)   # 🔥 folder मधले files घे

    return render_template("uploads.html", files=files)

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect("/login")

    file = request.files.get("file")

    if file and file.filename != "":
        filename = str(uuid.uuid4()) + "_" + file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO files(user,filename) VALUES(?,?)",
                  (session["user"], filename))
        conn.commit()
        conn.close()

        flash("File uploaded ✅")

    return redirect("/dashboard")

# ================= DELETE (FIXED 🔥) =================
from urllib.parse import unquote

@app.route("/delete/<path:filename>")
def delete_file(filename):
    if "user" not in session:
        return redirect("/login")

    filename = unquote(filename)

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    if os.path.exists(filepath):
        os.remove(filepath)

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM files WHERE filename=?", (filename,))
    conn.commit()
    conn.close()

    return redirect("/uploads")

# ================= DOWNLOAD =================
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)