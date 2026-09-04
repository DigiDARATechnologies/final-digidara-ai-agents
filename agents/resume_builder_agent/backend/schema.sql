CREATE DATABASE IF NOT EXISTS ai_resume_builder
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_resume_builder;

-- Users table (placeholder until merged with real LMS users table)
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_users_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Resumes table
CREATE TABLE resumes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  target_role VARCHAR(255),
  experience_level VARCHAR(20),
  template_choice VARCHAR(100) NOT NULL DEFAULT 'steady-form',
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  summary TEXT,
  profile_photo VARCHAR(500),
  declaration TEXT,
  ats_score INT,
  job_match_score INT,
  download_count INT NOT NULL DEFAULT 0,
  last_downloaded_at DATETIME,
  last_analyzed_at DATETIME,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_resumes_user_id (user_id),
  INDEX idx_resumes_status (status),
  INDEX idx_resumes_template_choice (template_choice),
  CONSTRAINT fk_resumes_user_id
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Personal info (1-to-1 with resume)
CREATE TABLE personal_info (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(50),
  location VARCHAR(255),
  links JSON,
  CONSTRAINT fk_personal_info_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Education (1-to-many)
CREATE TABLE education (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  school VARCHAR(255) NOT NULL,
  degree VARCHAR(255),
  field VARCHAR(255),
  start_date DATE,
  end_date DATE,
  cgpa VARCHAR(20),
  INDEX idx_education_resume_id (resume_id),
  CONSTRAINT fk_education_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Experience (1-to-many) with AI-generated bullets
CREATE TABLE experience (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  company VARCHAR(255) NOT NULL,
  role VARCHAR(255) NOT NULL,
  start_date DATE,
  end_date DATE,
  is_current BOOLEAN NOT NULL DEFAULT FALSE,
  raw_input TEXT,
  ai_generated_bullets JSON,
  INDEX idx_experience_resume_id (resume_id),
  CONSTRAINT fk_experience_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Skills (1-to-many)
CREATE TABLE skills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  skill_name VARCHAR(150) NOT NULL,
  INDEX idx_skills_resume_id (resume_id),
  CONSTRAINT fk_skills_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Certifications (1-to-many)
CREATE TABLE certifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  issuer VARCHAR(255),
  date DATE,
  INDEX idx_certifications_resume_id (resume_id),
  CONSTRAINT fk_certifications_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Projects (1-to-many)
CREATE TABLE projects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  INDEX idx_projects_resume_id (resume_id),
  CONSTRAINT fk_projects_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Languages (1-to-many) — was missing before, added now
-- Publications (1-to-many)
CREATE TABLE publications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  date DATE,
  INDEX idx_publications_resume_id (resume_id),
  CONSTRAINT fk_publications_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Achievements (1-to-many)
CREATE TABLE achievements (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  date DATE,
  INDEX idx_achievements_resume_id (resume_id),
  CONSTRAINT fk_achievements_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ATS analysis history (1-to-many)
CREATE TABLE ats_analyses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  analysis_type VARCHAR(40) NOT NULL,
  final_score INT NOT NULL,
  scoring_version VARCHAR(40) NOT NULL,
  job_description TEXT,
  breakdown JSON,
  matched_requirements JSON,
  missing_requirements JSON,
  recommendations JSON,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ats_analyses_resume_id (resume_id),
  INDEX idx_ats_analyses_user_id (user_id),
  CONSTRAINT fk_ats_analyses_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE languages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  language_name VARCHAR(100) NOT NULL,
  proficiency VARCHAR(50),
  INDEX idx_languages_resume_id (resume_id),
  CONSTRAINT fk_languages_resume_id
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
