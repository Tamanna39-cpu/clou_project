from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(_name_)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")  # fallback

# --- Database setup ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --- User model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    can_upload = db.Column(db.Boolean, default=False)

# --- Create DB and predefined users ---
with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        db.session.add_all([
            User(username="admin", password="admin123", can_upload=True),
            User(username="tamanna", password="secure456", can_upload=True),
            User(username="guest", password="guest123", can_upload=False)
        ])
        db.session.commit()

# --- AWS S3 client ---
s3 = boto3.client("s3")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# --- Routes ---

@app.route("/")
def intro():
    return render_template("intro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session["username"] = user.username
            session["can_upload"] = user.can_upload
        else:
            session["username"] = username
            session["can_upload"] = False

        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if not session.get("can_upload", False):
            flash("You are logged in but not allowed to upload files.", "error")
            return redirect(url_for("dashboard"))

        file = request.files.get("file")
        if not file:
            flash("No file part in the request.", "error")
            return redirect(url_for("dashboard"))

        if file.filename == '':
            flash("No file selected.", "error")
            return redirect(url_for("dashboard"))

        if not BUCKET_NAME:
            flash("S3 bucket name is not set. Check your .env file.", "error")
            return redirect(url_for("dashboard"))

        try:
            s3.upload_fileobj(file, BUCKET_NAME, file.filename)
            flash(f"File '{file.filename}' uploaded successfully!", "success")
        except Exception as e:
            flash(f"Error uploading file: {str(e)}", "error")

        return redirect(url_for("dashboard"))

    return render_template(
        "dashboard.html",
        username=session["username"],
        can_upload=session.get("can_upload", False)
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("intro"))

if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000, debug=True)
