"""Creates one demo course + one eligible student so the API can be exercised
end-to-end without a full admin/enrollment system in front of it.

Run: python -m scripts.seed_demo_data
"""
from datetime import datetime, timezone

from app.db.database import get_session, init_db
from app.db.models import Certificate, Course, CourseMedium, Enrollment, EnrollmentStatus, Student

DEMO_PHONE = "+911234567890"
DEMO_COURSE_NAME = "Python for Data Automation"


def main() -> None:
    init_db()
    session = get_session()
    try:
        course = session.query(Course).filter_by(name=DEMO_COURSE_NAME).first()
        if course is None:
            course = Course(name=DEMO_COURSE_NAME, medium=CourseMedium.local)
            session.add(course)
            session.flush()
            print(f"Created course: {course.name} ({course.id})")

        student = session.query(Student).filter_by(phone=DEMO_PHONE).first()
        if student is None:
            student = Student(name="Demo Student", phone=DEMO_PHONE)
            session.add(student)
            session.flush()
            print(f"Created student: {student.name} ({student.id})")

        enrollment = (
            session.query(Enrollment)
            .filter_by(student_id=student.id, course_id=course.id)
            .first()
        )
        if enrollment is None:
            enrollment = Enrollment(
                student_id=student.id,
                course_id=course.id,
                status=EnrollmentStatus.completed,
                completed_at=datetime.now(timezone.utc),
            )
            session.add(enrollment)
            print("Created completed enrollment.")

        certificate = (
            session.query(Certificate)
            .filter_by(student_id=student.id, course_id=course.id)
            .first()
        )
        if certificate is None:
            certificate = Certificate(
                student_id=student.id,
                course_id=course.id,
                certificate_id=f"CERT-DEMO-{student.id[:8]}",
            )
            session.add(certificate)
            print("Issued certificate.")

        session.commit()
        print("\nSeed complete. Use this to call POST /api/eligibility/check:")
        print(f'  {{"name": "Demo Student", "phone": "{DEMO_PHONE}", "course_name": "{DEMO_COURSE_NAME}"}}')
    finally:
        session.close()


if __name__ == "__main__":
    main()
