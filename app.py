from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader
from datetime import datetime
from flask import send_from_directory
import os

app = Flask(__name__)
app.secret_key = "mysecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(100), unique=True)

    password = db.Column(db.String(100))

class Note(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    filename = db.Column(
        db.String(200)
    )

    username = db.Column(
        db.String(100)
    )

    category = db.Column(
        db.String(50)
    )

    uploaded_at = db.Column(
        db.DateTime
    )

    summary = db.Column(
        db.Text
    )

    text = db.Column(
        db.Text
    )

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            session["username"] = user.username
            flash("Login Successful!")
            return redirect(url_for("dashboard"))

        else:

            flash("Invalid Email or Password")
            return redirect(
              url_for("login")
            )

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:
            return "Email already registered. Please login."

        password = generate_password_hash(
            request.form["password"]
        )

        new_user = User(
            username=username,
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return "User Registered Successfully!"

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():

    category = request.args.get("category")

    if "username" in session:

        if category:

            notes = Note.query.filter_by(
                username=session["username"],
                category=category
            ).all()

        else:

            notes = Note.query.filter_by(
                username=session["username"]
            ).all()

        total_notes = len(notes)

        # Analytics Counts
        python_notes = Note.query.filter_by(
            username=session["username"],
            category="Python"
        ).count()

        dbms_notes = Note.query.filter_by(
            username=session["username"],
            category="DBMS"
        ).count()

        ai_notes = Note.query.filter_by(
            username=session["username"],
            category="AI"
        ).count()

        maths_notes = Note.query.filter_by(
            username=session["username"],
            category="Maths"
        ).count()

        return render_template(
            "dashboard.html",
            username=session["username"],
            notes=notes,
            total_notes=total_notes,
            python_notes=python_notes,
            dbms_notes=dbms_notes,
            ai_notes=ai_notes,
            maths_notes=maths_notes
        )

    return redirect(url_for("login"))

@app.route("/profile")
def profile():

    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(
        username=session["username"]
    ).first()

    return render_template(
        "profile.html",
        user=user
    )

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():

    if "username" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(
        username=session["username"]
    ).first()

    if request.method == "POST":

        user.username = request.form["username"]
        user.email = request.form["email"]

        db.session.commit()

        session["username"] = user.username

        flash("Profile Updated Successfully!")

        return redirect(url_for("profile"))

    return render_template(
        "edit_profile.html",
        user=user
    )

@app.route("/logout")
def logout():

    session.pop("username", None)

    return redirect(url_for("home"))

@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        file = request.files["pdf"]
        category = request.form["category"]
        if not file.filename.endswith(".pdf"):

           flash("Only PDF files are allowed!")

           return redirect(
              url_for("upload")
           )
        filepath = f"uploads/{file.filename}"

        file.save(filepath)

        # Read PDF
        reader = PdfReader(filepath)

        text = ""

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text

        # Create summary
        words = text.split()

        summary = " ".join(words[:150])
        quiz = []
        sentences = text.split(".")

        for sentence in sentences[:5]:

           if len(sentence.split()) > 5:

              quiz.append(sentence.strip())

        # Save note in database
        new_note = Note(
            filename=file.filename,
            username=session["username"],
            summary=summary,
            text=text,
            category=category
        )

        db.session.add(new_note)
        db.session.commit()

        return render_template(
            "summary.html",
            summary=summary
        )

    return render_template("upload.html")


@app.route("/view_summary/<int:id>")
def view_summary(id):

    note = Note.query.get(id)

    if not note:
        return "Note not found"

    return render_template(
        "summary.html",
        summary=note.summary
    )

@app.route("/quiz")
def quiz():

    note = Note.query.order_by(
        Note.id.desc()
    ).first()

    if not note:
        return "No notes uploaded yet."

    sentences = note.text.split(".")

    questions = []

    for sentence in sentences[:5]:

        sentence = sentence.strip()

        if len(sentence) > 20:

            questions.append(sentence)

    return render_template(
        "quiz.html",
        quiz=questions
    )

@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():

    score = 0

    for i in range(1, 6):

        answer = request.form.get(
            f"q{i}"
        )

        if answer == "A":
            score += 1

    return f"""
    <h1>Your Score: {score}/5</h1>

    <a href="/dashboard">
        Back to Dashboard
    </a>
    """

@app.route("/search", methods=["GET", "POST"])
def search():

    results = []

    if request.method == "POST":

        keyword = request.form["keyword"]

        results = Note.query.filter(
            Note.text.contains(keyword)
        ).all()

    return render_template(
        "search.html",
        results=results
    )

@app.route("/download/<filename>")
def download_file(filename):

    return send_from_directory(
        "uploads",
        filename,
        as_attachment=True
    )

@app.route("/delete_note/<int:id>")
def delete_note(id):

    note = Note.query.get(id)

    if note:

        filepath = f"uploads/{note.filename}"

        if os.path.exists(filepath):
            os.remove(filepath)

        db.session.delete(note)

        db.session.commit()

    return redirect(url_for("dashboard"))

@app.route("/change_password", methods=["GET", "POST"])
def change_password():

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        old_password = request.form["old_password"]
        new_password = request.form["new_password"]

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if check_password_hash(
            user.password,
            old_password
        ):

            user.password = generate_password_hash(
                new_password
            )

            db.session.commit()

            return "Password Changed Successfully!"

        else:

            return "Old Password Incorrect"

    return render_template(
        "change_password.html"
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)