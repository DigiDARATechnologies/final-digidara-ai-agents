"""Add a new eligible student (enrolled + completed + certified) for a course.

Usage:
  python -m scripts.add_student --name "Ravi Kumar" --email "ravi@example.com" --phone "+919876543210" --course "Python for Data Automation"

Optional:
  --medium local|api          (default: local, only used if the course doesn't exist yet)
  --not-completed              (leave enrollment as active, skip completed_at/certificate)
"""
import argparse
from datetime import datetime, timezone

from app.db.database import get_session, init_db
from app.db.models import Certificate, Course, CourseMedium, Enrollment, EnrollmentStatus, Student


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--email")
    parser.add_argument("--phone", required=True)
    parser.add_argument("--course", required=True)
    parser.add_argument("--medium", default="local", choices=["local", "api"])
    parser.add_argument("--not-completed", action="store_true",
                         help="Leave enrollment active instead of completed/certified")
    args = parser.parse_args()

    init_db()
    session = get_session()
    try:
        course = session.query(Course).filter_by(name=args.course).first()
        if course is None:
            course = Course(name=args.course, medium=CourseMedium[args.medium])
            session.add(course)
            session.flush()
            print(f"Created course: {course.name} ({course.id})")

        student = session.query(Student).filter_by(phone=args.phone).first()
        if student is None:
            student = Student(name=args.name, email=args.email, phone=args.phone)
            session.add(student)
            session.flush()
            print(f"Created student: {student.name} ({student.id})")
        else:
            student.name = args.name
            if args.email:
                student.email = args.email
            print(f"Student already exists: {student.name} ({student.id})")

        enrollment = (
            session.query(Enrollment)
            .filter_by(student_id=student.id, course_id=course.id)
            .first()
        )
        if enrollment is None:
            enrollment = Enrollment(
                student_id=student.id,
                course_id=course.id,
                status=EnrollmentStatus.in_progress if args.not_completed else EnrollmentStatus.completed,
                completed_at=None if args.not_completed else datetime.now(timezone.utc),
            )
            session.add(enrollment)
            print(f"Created enrollment (status={enrollment.status.value}).")
        else:
            print(f"Enrollment already exists (status={enrollment.status.value}).")

        if not args.not_completed:
            certificate = (
                session.query(Certificate)
                .filter_by(student_id=student.id, course_id=course.id)
                .first()
            )
            if certificate is None:
                certificate = Certificate(
                    student_id=student.id,
                    course_id=course.id,
                    certificate_id=f"CERT-{student.id[:8]}-{course.id[:8]}",
                )
                session.add(certificate)
                print("Issued certificate.")

        session.commit()
        print("\nDone. Eligibility check payload:")
        print(f'  {{"name": "{student.name}", "phone": "{student.phone}", "course_name": "{course.name}"}}')
    finally:
        session.close()


if __name__ == "__main__":
    main()
