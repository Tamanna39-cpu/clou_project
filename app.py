from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")  # fallback if .env missing

# --- Database ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    can_upload = db.Column(db.Boolean, default=False)

# Create DB + add predefined users
with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        db.session.add_all([
            User(username="admin", password="admin123", can_upload=True),
            User(username="tamanna", password="secure456", can_upload=True),
            User(username="guest", password="guest123", can_upload=False)
        ])
        db.session.commit()

# AWS S3 client (uses IAM Role or credentials in environment)
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

        # ✅ Check if user exists in DB
        user = User.query.filter_by(username=username, password=password).first()

        if user:  # user is in database
            session["username"] = user.username
            session["can_upload"] = user.can_upload
        else:  # user not in database
            session["username"] = username   # still allow login
            session["can_upload"] = False    # but no upload rights

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
        if file and file.filename:
            try:
                s3.upload_fileobj(file, BUCKET_NAME, file.filename)
                flash(f"File {file.filename} uploaded successfully!", "success")
            except Exception as e:
                flash(f"Error uploading file: {str(e)}", "error")
        else:
            flash("Please select a file.", "error")
        return redirect(url_for("dashboard"))

    return render_template("dashboard.html",
                           username=session["username"],
                           can_upload=session.get("can_upload", False))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("intro"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)