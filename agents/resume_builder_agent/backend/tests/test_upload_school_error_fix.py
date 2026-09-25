import pytest
from app.services import import_review
from app.routes import resumes


def test_section_23_test_1_python_developer_no_school_succeeds(client):
    """Test 1 - Python Developer: Upload resume without school succeeds, no 'Missing required field(s): school'."""
    resume_text = """Name: Arjun Kumar
Role: Python Developer
Email: arjun@example.com
Phone: +91 9876543210

Summary
Python developer with 2 years of experience building APIs and database systems.

Skills
Python, Flask, Django, SQL, PostgreSQL, Docker, Git

Experience
Backend Developer - TechCorp
2023 - Present
Built REST APIs using Flask and PostgreSQL.

Projects
Inventory Management System
Built automated inventory tracking using Django and React.
"""
    parsed, unmapped = import_review.parse_resume_text(resume_text)
    parsed["targetRole"] = "Python Developer"
    payload = import_review.map_import_to_resume_payload(
        parsed,
        filename="python_dev_resume.pdf",
        user_id="test-python-dev",
    )
    # The payload must succeed creating a resume in the database
    response = client.post("/api/resume", json=payload)
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["target_role"] == "Python Developer"
    assert data["education"] == []


def test_section_23_test_2_no_education_succeeds(client):
    """Test 2 - No Education: Name, Skills, Experience, Projects -> education: [] with no failure."""
    resume_payload = {
        "user_id": "test-no-edu",
        "title": "Python Developer Resume",
        "target_role": "Python Developer",
        "experience_level": "experienced",
        "personal_info": {
            "name": "Arjun Kumar",
            "email": "arjun@example.com",
            "phone": "9876543210",
        },
        "education": [],
        "skills": [{"skill_name": "Python"}, {"skill_name": "SQL"}],
        "experience": [{
            "company": "Tech Solutions",
            "role": "Python Developer",
            "start_date": "2023-01-01",
            "end_date": "Present",
            "raw_input": "Built backend services",
        }],
        "projects": [{
            "title": "Inventory System",
            "description": "Django inventory app",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["education"] == []


def test_section_23_test_3_ug_only():
    """Test 3 - UG Only: BCA, ABC College, 78% percentage."""
    resume_text = """Name: Arjun Kumar
Email: arjun@example.com

Education
Bachelor of Computer Applications
ABC College
2019 - 2022
Percentage: 78%
"""
    parsed, _ = import_review.parse_resume_text(resume_text)
    payload = import_review.map_import_to_resume_payload(parsed, "ug_resume.pdf", "test-user")
    assert len(payload["education"]) == 1
    edu = payload["education"][0]
    assert "BCA" in edu["degree"] or "Bachelor of Computer Applications" in edu["degree"]
    assert edu["school"] == "ABC College"
    assert edu["institution"] == "ABC College"
    assert edu["level"] == "UG"
    assert "78%" in edu["cgpa"]


def test_section_23_test_4_pg_only():
    """Test 4 - PG Only: MCA, XYZ University, 8.1 CGPA."""
    resume_text = """Name: Priya S
Email: priya@example.com

Education
Master of Computer Applications
XYZ University
2022 - 2024
CGPA: 8.1
"""
    parsed, _ = import_review.parse_resume_text(resume_text)
    payload = import_review.map_import_to_resume_payload(parsed, "pg_resume.pdf", "test-user")
    assert len(payload["education"]) == 1
    edu = payload["education"][0]
    assert "MCA" in edu["degree"] or "Master of Computer Applications" in edu["degree"]
    assert edu["school"] == "XYZ University"
    assert edu["level"] == "PG"
    assert edu["cgpa"] == "8.1"


def test_section_23_test_5_ug_and_pg_separately():
    """Test 5 - UG + PG: Both preserved separately."""
    resume_text = """Name: Swetha S
Email: swetha@example.com

Education
Master of Computer Applications
KSR College of Engineering
2023 - 2025
CGPA: 8.5

Bachelor of Computer Applications
Nandha Arts and Science College
2020 - 2023
Percentage: 82%
"""
    parsed, _ = import_review.parse_resume_text(resume_text)
    payload = import_review.map_import_to_resume_payload(parsed, "ug_pg_resume.pdf", "test-user")
    assert len(payload["education"]) >= 2
    degrees = [e["degree"] for e in payload["education"]]
    assert any("Master" in d or "MCA" in d for d in degrees)
    assert any("Bachelor" in d or "BCA" in d for d in degrees)


def test_section_23_test_6_missing_cgpa(client):
    """Test 6 - Missing CGPA: Resume has education but no CGPA -> cgpa='' without failure."""
    resume_payload = {
        "user_id": "test-no-cgpa",
        "title": "Resume Without CGPA",
        "personal_info": {"name": "Test User", "email": "test@example.com"},
        "education": [{
            "institution": "ABC Institute",
            "degree": "B.Tech Computer Science",
            "start_date": "2020",
            "end_date": "2024",
            "cgpa": "",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    edu = response.get_json()["data"]["education"][0]
    assert edu["cgpa"] is None or edu["cgpa"] == ""
    assert edu["school"] == "ABC Institute"


def test_section_23_test_7_missing_percentage(client):
    """Test 7 - Missing Percentage: percentage='' without failure."""
    resume_payload = {
        "user_id": "test-no-pct",
        "title": "Resume Without Percentage",
        "personal_info": {"name": "Test User", "email": "test@example.com"},
        "education": [{
            "school": "ABC Institute",
            "degree": "B.E. Computer Science",
            "percentage": "",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    edu = response.get_json()["data"]["education"][0]
    assert edu["percentage"] == ""


def test_section_23_test_8_missing_school_zero_occurrences(client):
    """Test 8 - Missing School: explicitly test a resume with zero occurrences of 'school'."""
    resume_payload = {
        "user_id": "test-zero-school",
        "title": "Zero School Resume",
        "personal_info": {"name": "Candidate", "email": "cand@example.com"},
        "education": [{
            "degree": "Self-Taught Python Certification",
            "field": "Software Engineering",
            "start_date": "2023",
            "end_date": "2024",
        }],
    }
    # Must NOT fail with "Missing required field(s): school"
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    edu = response.get_json()["data"]["education"][0]
    assert edu["school"] == ""
    assert edu["degree"] == "Self-Taught Python Certification"


def test_section_23_test_12_certifications(client):
    """Test 12 - Certifications: resume contains certifications -> preserved without failure."""
    resume_payload = {
        "user_id": "test-certs",
        "title": "Certified Developer",
        "personal_info": {"name": "Dev", "email": "dev@example.com"},
        "certifications": [{
            "name": "AWS Certified Developer - Associate",
            "issuer": "Amazon Web Services",
            "date": "2024-05-01",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    certs = response.get_json()["data"]["certifications"]
    assert len(certs) == 1
    assert certs[0]["name"] == "AWS Certified Developer - Associate"
    assert certs[0]["issuer"] == "Amazon Web Services"


def test_section_23_test_13_achievements(client):
    """Test 13 - Achievements: resume contains achievements -> preserved without failure."""
    resume_payload = {
        "user_id": "test-achievements",
        "title": "Achiever Resume",
        "personal_info": {"name": "Dev", "email": "dev@example.com"},
        "achievements": [{
            "title": "First Place - Hackathon 2024",
            "description": "Built AI agent prototype within 24 hours.",
            "date": "2024-03-15",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    achievements = response.get_json()["data"]["achievements"]
    assert len(achievements) == 1
    assert achievements[0]["title"] == "First Place - Hackathon 2024"


def test_section_23_test_14_existing_complete_resume(client):
    """Test 14 - Existing Complete Resume: all sections preserved."""
    resume_payload = {
        "user_id": "test-complete",
        "title": "Complete Resume",
        "target_role": "Python Developer",
        "experience_level": "experienced",
        "summary": "Experienced Python Engineer.",
        "personal_info": {
            "name": "Arjun Kumar",
            "email": "arjun@example.com",
            "phone": "9876543210",
            "location": "Chennai, India",
            "links": [
                "https://linkedin.com/in/arjunkumar",
                "https://github.com/arjunkumar",
                "https://arjun.dev",
            ],
        },
        "education": [{
            "school": "Anna University",
            "degree": "B.E. Computer Science",
            "start_date": "2018",
            "end_date": "2022",
            "cgpa": "8.5",
        }],
        "skills": [{"skill_name": "Python"}, {"skill_name": "Flask"}],
        "experience": [{
            "company": "Tech Corp",
            "role": "Python Developer",
            "start_date": "2022-06-01",
            "end_date": "Present",
            "raw_input": "Developed REST APIs",
        }],
        "projects": [{
            "title": "API Gateway",
            "description": "High performance gateway",
        }],
        "certifications": [{
            "name": "AWS Certified Solutions Architect",
            "issuer": "AWS",
            "date": "2023-01-01",
        }],
        "achievements": [{
            "title": "Employee of the Year",
            "description": "Recognized for API architecture excellence",
        }],
    }
    response = client.post("/api/resume", json=resume_payload)
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["target_role"] == "Python Developer"
    assert data["personal_info"]["name"] == "Arjun Kumar"
    assert len(data["personal_info"]["links"]) == 3
    assert len(data["education"]) == 1
    assert len(data["skills"]) == 2
    assert len(data["experience"]) == 1
    assert len(data["projects"]) == 1
    assert len(data["certifications"]) == 1
    assert len(data["achievements"]) == 1
