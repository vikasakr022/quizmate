from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash
)
import mysql.connector
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get(
    "QUIZMATE_SECRET_KEY",
    "change-this-secret-before-deployment"
)
# ADMIN LOGIN CONFIGURATION

ADMIN_USERNAME = os.environ.get(
    "QUIZMATE_ADMIN_USERNAME",
    "lecturer"
)

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$5msuI76JdbW6O38N$035a6cc260ccbccb95b0bf6ef36a81422fdcf4f6e789aa95d6643f2adc0fe572962bcafaa796eae09d689486509294a8adbfcbfa80ad54d98a563288ca35df83"

# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3307")),
        user=os.environ.get("DB_USER", "quizmate_app"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "quizmate_db")
    )


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# SUBJECTS PAGE
# ==========================================

@app.route("/subjects-page")
def subjects_page():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT subject_id, subject_name
            FROM subjects
            ORDER BY subject_name
        """)

        subjects = cursor.fetchall()

        return render_template(
            "subjects.html",
            subjects=subjects
        )

    except Exception as e:
        return f"Error loading subjects: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ==========================================
# SUBJECTS API
# ==========================================

@app.route("/api/subjects")
@app.route("/subjects")
def get_subjects():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT subject_id, subject_name
            FROM subjects
            ORDER BY subject_name
        """)

        return jsonify(cursor.fetchall())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
            # ==========================================
# ADD SUBJECT
# ==========================================

@app.route("/admin/add-subject", methods=["GET", "POST"])
def add_subject():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        subject_name = request.form.get(
            "subject_name", ""
        ).strip()

        if not subject_name:
            flash("Please enter a subject name.")
            return redirect(url_for("add_subject"))

        db = None
        cursor = None

        try:
            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                "INSERT INTO subjects (subject_name) VALUES (%s)",
                (subject_name,)
            )
            db.commit()

            flash("Subject added successfully!")

        except mysql.connector.IntegrityError:
            flash("This subject may already exist.")

        except Exception as e:
            if db:
                db.rollback()
            return f"Error adding subject: {e}", 500

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

        return redirect(url_for("add_subject"))

    return render_template("add_subject.html")

# ==========================================
# DELETE QUESTION
# ==========================================

@app.route(
    "/admin/delete-question/<int:question_id>",
    methods=["POST"]
)
def delete_question(question_id):
    if not session.get("admin_logged_in"):
        return jsonify({
            "error": "Lecturer login required."
        }), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "SELECT question_id FROM questions WHERE question_id = %s",
            (question_id,)
        )

        question = cursor.fetchone()

        if not question:
            return jsonify({
                "error": "Question not found."
            }), 404

        cursor.execute(
            "DELETE FROM questions WHERE question_id = %s",
            (question_id,)
        )

        db.commit()

        return jsonify({
            "message": "Question deleted successfully!"
        }), 200

    except Exception:
        if db:
            db.rollback()

        app.logger.exception("Error deleting question")

        return jsonify({
            "error": "Unable to delete question. Please try again."
        }), 500

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()
            # ==========================================
# DELETE SUBJECT
# ==========================================

@app.route("/admin/delete-subject/<int:subject_id>", methods=["POST"])
def delete_subject(subject_id):

    if not session.get("admin_logged_in"):
        return jsonify({"error": "Lecturer login required."}), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Check whether the subject exists
        cursor.execute(
            "SELECT subject_id FROM subjects WHERE subject_id = %s",
            (subject_id,)
        )

        if not cursor.fetchone():
            return jsonify({"error": "Subject not found."}), 404

        # Prevent deletion if questions belong to this subject
        cursor.execute(
            "SELECT COUNT(*) FROM questions WHERE subject_id = %s",
            (subject_id,)
        )

        question_count = cursor.fetchone()[0]

        if question_count > 0:
            return jsonify({
                "error": (
                    f"This subject has {question_count} questions. "
                    "Delete its questions first."
                )
            }), 409

        # Delete the subject
        cursor.execute(
            "DELETE FROM subjects WHERE subject_id = %s",
            (subject_id,)
        )

        db.commit()

        return jsonify({
            "message": "Subject deleted successfully!"
        }), 200

    except Exception:
        if db:
            db.rollback()

        app.logger.exception("Error deleting subject")

        return jsonify({
            "error": "Unable to delete subject. Please try again."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ADMIN LOGIN
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "GET":
        if session.get("admin_logged_in"):
            return redirect(url_for("admin"))

        return render_template("admin_login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if (
        username == ADMIN_USERNAME
        and ADMIN_PASSWORD_HASH
        and check_password_hash(ADMIN_PASSWORD_HASH, password)
    ):
        session["admin_logged_in"] = True
        flash("Login successful!")
        return redirect(url_for("admin"))

    flash("Invalid username or password.")
    return redirect(url_for("admin_login"))


# ADMIN LOGOUT
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("You have been logged out.")
    return redirect(url_for("admin_login"))

# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT COUNT(*) AS total FROM subjects"
        )
        total_subjects = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM questions"
        )
        total_questions = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM students"
        )
        total_students = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total FROM quiz_results"
        )
        total_results = cursor.fetchone()["total"]

        return render_template(
            "admin.html",
            total_subjects=total_subjects,
            total_questions=total_questions,
            total_students=total_students,
            total_results=total_results
        )

    except Exception as e:
        return f"Error loading admin dashboard: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
# ==========================================
# VIEW ALL STUDENT RESULTS
# ==========================================

@app.route("/admin/all-results")
def admin_all_results():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                qr.result_id,
                COALESCE(s.name, 'Guest') AS student_name,
                COALESCE(s.email, 'N/A') AS student_email,
                qr.subject_name,
                qr.score,
                qr.total_questions,
                qr.completed_at
            FROM quiz_results qr
            LEFT JOIN students s
                ON qr.student_id = s.student_id
            ORDER BY qr.completed_at DESC
        """)

        results = cursor.fetchall()

        return render_template(
            "all_results.html",
            results=results
        )

    except Exception as e:
        app.logger.exception("Unable to load student results")
        return f"Error loading student results: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ==========================================
# ADD QUESTION PAGE
# ==========================================

@app.route("/admin/add-question", methods=["GET", "POST"])
def add_question():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "GET":
        db = None
        cursor = None

        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT subject_id, subject_name
                FROM subjects
                ORDER BY subject_name
            """)

            subjects = cursor.fetchall()

            return render_template(
                "add_questions.html",
                subjects=subjects,
                message=None
            )

        except Exception as e:
            return f"Error loading question form: {e}", 500

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # Read submitted form values
    subject_id = request.form.get("subject", "").strip()
    question_text = request.form.get(
        "question_text", ""
    ).strip()

    option_a = request.form.get("option_a", "").strip()
    option_b = request.form.get("option_b", "").strip()
    option_c = request.form.get("option_c", "").strip()
    option_d = request.form.get("option_d", "").strip()

    correct_answer = request.form.get(
        "correct_answer", ""
    ).strip()

    # Validate all fields
    if not all([
        subject_id,
        question_text,
        option_a,
        option_b,
        option_c,
        option_d,
        correct_answer
    ]):
        return "Please fill in all fields.", 400

    if correct_answer not in ["1", "2", "3", "4"]:
        return "Please select a valid correct answer.", 400

    try:
        subject_id = int(subject_id)

        if subject_id <= 0:
            return "Invalid subject selected.", 400

    except ValueError:
        return "Invalid subject ID.", 400

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Confirm that the selected subject exists
        cursor.execute(
            "SELECT subject_id FROM subjects WHERE subject_id = %s",
            (subject_id,)
        )

        if not cursor.fetchone():
            return "Selected subject does not exist.", 400

        # Save the question
        sql = """
            INSERT INTO questions (
                subject_id,
                question_text,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            subject_id,
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer
        )

        cursor.execute(sql, values)
        db.commit()

        return redirect(
            url_for("add_question", success="1")
        )

    except Exception as e:
        if db:
            db.rollback()

        return f"Error adding question: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ==========================================
# MANAGE QUESTIONS PAGE
# ==========================================

@app.route("/admin/manage-questions")
def manage_questions():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT subject_id, subject_name
            FROM subjects
            ORDER BY subject_name
        """)

        subjects = cursor.fetchall()

        return render_template(
            "manage_questions.html",
            subjects=subjects
        )

    except Exception as e:
        return f"Error loading questions page: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ==========================================
# QUESTIONS API
# ==========================================

@app.route("/api/questions")
@app.route("/questions")
def get_questions():
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        subject_id = request.args.get("subject_id")

        if subject_id:
            try:
                subject_id = int(subject_id)

                if subject_id <= 0:
                    return jsonify({
                        "error": "Invalid subject ID"
                    }), 400

            except ValueError:
                return jsonify({
                    "error": "Invalid subject ID"
                }), 400

            cursor.execute("""
                SELECT *
                FROM questions
                WHERE subject_id = %s
                ORDER BY question_id DESC
            """, (subject_id,))

        else:
            cursor.execute("""
                SELECT *
                FROM questions
                ORDER BY question_id DESC
            """)

        return jsonify(cursor.fetchall())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
 

# ==========================================
# STUDENT LOGIN PAGE
# ==========================================

@app.route("/student-login", methods=["GET", "POST"])
def student_login():
    if request.method == "GET":
        return render_template("student_login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Please enter email and password.")
        return redirect(url_for("student_login"))

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT student_id, name, email, password FROM students WHERE email = %s",
            (email,)
        )
        student = cursor.fetchone()

        if student and check_password_hash(student["password"], password):
            session["student_id"] = student["student_id"]
            session["student_name"] = student["name"]
            return redirect(url_for("subjects_page"))

        flash("Invalid email or password.")
        return redirect(url_for("student_login"))

    except Exception as e:
        return f"Student login error: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

            # ==========================================
# STUDENT REGISTRATION
# ==========================================

@app.route("/student-register", methods=["GET", "POST"])
def student_register():

    if request.method == "GET":
        return render_template("student_register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        flash("Please fill in all fields.")
        return redirect(url_for("student_register"))

    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return redirect(url_for("student_register"))

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO students (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (name, email, generate_password_hash(password))
        )

        db.commit()

        flash("Registration successful! Please login.")
        return redirect(url_for("student_login"))

    except mysql.connector.IntegrityError:
        if db:
            db.rollback()

        flash("This email is already registered.")
        return redirect(url_for("student_register"))

    except Exception as e:
        if db:
            db.rollback()

        return f"Registration error: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
# ==========================================
# QUIZ PAGE
# ==========================================

@app.route("/quiz/<int:subject_id>")
def quiz_page(subject_id):
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM questions
            WHERE subject_id = %s
            ORDER BY question_id
        """, (subject_id,))

        questions = cursor.fetchall()

        if not questions:
            return "No questions available for this subject.", 404

        return render_template(
            "quiz.html",
            questions=questions,
            subject_id=subject_id
        )

    except Exception as e:
        return f"Error loading quiz: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# ==========================================
# RESULTS PAGE
# ==========================================

@app.route("/results/<int:subject_id>")
def results_page(subject_id):
    if not session.get("student_id") and not session.get("admin_logged_in"):
        return redirect(url_for("student_login"))
    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                qr.result_id,
                qr.student_id,
                COALESCE(s.name, 'Guest') AS student_name,
                COALESCE(s.email, 'N/A') AS student_email,
                qr.subject_name,
                qr.score,
                qr.total_questions,
                qr.completed_at
            FROM quiz_results qr
            LEFT JOIN students s
                ON qr.student_id = s.student_id
           WHERE qr.subject_name = (
    SELECT subject_name
    FROM subjects
    WHERE subject_id = %s
)
AND (
    qr.student_id = %s
    OR %s = 1
)
ORDER BY qr.completed_at DESC
      """, (
    subject_id,
    session.get("student_id", 0),
    1 if session.get("admin_logged_in") else 0
))

        results = cursor.fetchall()
        results = [dict(row) for row in results]

        score = request.args.get("score", default=0, type=int)
        total_questions = request.args.get(
            "total", default=0, type=int
        )

        return render_template(
            "results.html",
            score=score,
            total_questions=total_questions,
            results=results
        )

    except Exception as e:
        return f"Error loading results: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ==========================================
# SUBMIT QUIZ
# ==========================================

@app.route("/submit-quiz", methods=["POST"])
def submit_quiz():
    if not session.get("student_id"):
        return redirect(url_for("student_login"))
    subject_id = request.form.get("subject_id", "").strip()

    if not subject_id:
        return "Subject ID is missing.", 400

    try:
        subject_id = int(subject_id)

        if subject_id <= 0:
            return "Invalid subject ID.", 400

    except ValueError:
        return "Invalid subject ID.", 400

    db = None
    cursor = None

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT subject_name
            FROM subjects
            WHERE subject_id = %s
        """, (subject_id,))

        subject = cursor.fetchone()

        if not subject:
            return "Subject not found.", 404

        subject_name = subject["subject_name"]

        cursor.execute("""
            SELECT question_id, correct_answer
            FROM questions
            WHERE subject_id = %s
        """, (subject_id,))

        questions = cursor.fetchall()

        if not questions:
            return "No questions available for this quiz.", 400

        score = 0
        total_questions = len(questions)

        for question in questions:
            question_id = str(question["question_id"])

            selected_answer = request.form.get(
                question_id, ""
            ).strip()

            correct_answer = str(
                question["correct_answer"]
            ).strip()

            if selected_answer == correct_answer:
                score += 1

        cursor.execute("""
            INSERT INTO quiz_results (
                student_id,
                subject_name,
                score,
                total_questions
            )
            VALUES (%s, %s, %s, %s)
        """, (
            session.get("student_id"),
            subject_name,
            score,
            total_questions
        ))

        db.commit()

        return redirect(
            url_for(
                "results_page",
                subject_id=subject_id,
                score=score,
                total=total_questions
            )
        )

    except Exception as e:
        if db:
            db.rollback()

        return f"Error submitting quiz: {e}", 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)