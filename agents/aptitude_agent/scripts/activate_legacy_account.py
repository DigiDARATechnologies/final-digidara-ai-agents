"""One-time interactive activation for accounts created before native auth."""
from getpass import getpass
from werkzeug.security import generate_password_hash
from app import app
from backend.app.extensions import db
from backend.app.models import Student


def main():
    email=input("Existing learner email: ").strip().lower()
    password=getpass("New password (8-128 characters): ")
    confirmation=getpass("Confirm password: ")
    if password!=confirmation:raise SystemExit("Passwords do not match.")
    if not 8<=len(password)<=128:raise SystemExit("Password must contain 8 to 128 characters.")
    with app.app_context():
        student=Student.query.filter_by(email=email).first()
        if not student:raise SystemExit("No existing learner account uses that email.")
        if student.password_hash:raise SystemExit("This account already has native authentication. Use Login.")
        student.password_hash=generate_password_hash(password);student.token_version+=1;db.session.commit()
        print(f"Activated AptiDARA account for {student.name}.")


if __name__=="__main__":main()
