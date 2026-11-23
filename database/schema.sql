-- UdM QA Feedback System
-- Reference schema. SQLAlchemy models and startup migrations are authoritative.
-- Do not use this file to replace an existing research database.
-- Departments, aspects, thresholds, and intervention_rules are DATA, not code.
-- After the client interview, UPDATE these rows instead of rewriting the website.
--
-- Duplicate submission prevention: Application-level check in _get_or_create_respondent
-- uses applicable areas (15 or 16) and rejects repeated respondent/area pairs.

CREATE DATABASE IF NOT EXISTS udm_qa_demo
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE udm_qa_demo;

CREATE TABLE IF NOT EXISTS departments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(160) NOT NULL,
  description VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS aspects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(160) NOT NULL,
  description VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(160) NOT NULL,
  -- Highest to lowest: executive_director, admin, assistant (Staff), viewer.
  role VARCHAR(32) NOT NULL DEFAULT 'viewer',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  token_version INT NOT NULL DEFAULT 0,
  failed_logins INT NOT NULL DEFAULT 0,
  locked_until DATETIME NULL,
  department_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_users_department FOREIGN KEY (department_id) REFERENCES departments(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS respondents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_number VARCHAR(32) NOT NULL UNIQUE,
  institutional_email VARCHAR(160) NOT NULL UNIQUE,
  college VARCHAR(16) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS colleges (
  code VARCHAR(16) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  numeric_code VARCHAR(2) NULL UNIQUE,
  is_active TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS college_headcounts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  college VARCHAR(16) NOT NULL UNIQUE,
  headcount INT NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  department_id INT NOT NULL,
  aspect_id INT NULL,
  respondent_id INT NULL,
  comment TEXT NOT NULL,
  rating INT CHECK (rating BETWEEN 1 AND 5),
  rating_1 INT CHECK (rating_1 BETWEEN 1 AND 5),
  rating_2 INT CHECK (rating_2 BETWEEN 1 AND 5),
  rating_3 INT CHECK (rating_3 BETWEEN 1 AND 5),
  student_number VARCHAR(32) NULL,
  consent TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_feedback_department FOREIGN KEY (department_id) REFERENCES departments(id),
  CONSTRAINT fk_feedback_aspect FOREIGN KEY (aspect_id) REFERENCES aspects(id),
  CONSTRAINT fk_feedback_respondent FOREIGN KEY (respondent_id) REFERENCES respondents(id),
  INDEX idx_feedback_created (created_at),
  INDEX idx_feedback_dept (department_id),
  INDEX idx_feedback_respondent (respondent_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feedback_labels (
  id INT AUTO_INCREMENT PRIMARY KEY,
  feedback_id INT NOT NULL UNIQUE,
  aspect_id INT NOT NULL,
  sentiment ENUM('positive', 'negative', 'constructive') NOT NULL,
  aspect_confidence FLOAT NOT NULL DEFAULT 0,
  sentiment_confidence FLOAT NOT NULL DEFAULT 0,
  aspect_source ENUM('student', 'model') NOT NULL DEFAULT 'model',
  CONSTRAINT fk_labels_feedback FOREIGN KEY (feedback_id) REFERENCES feedback(id) ON DELETE CASCADE,
  CONSTRAINT fk_labels_aspect FOREIGN KEY (aspect_id) REFERENCES aspects(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS thresholds (
  id INT AUTO_INCREMENT PRIMARY KEY,
  aspect_id INT NOT NULL UNIQUE,
  min_count INT NOT NULL DEFAULT 3,
  window_days INT NOT NULL DEFAULT 14,
  include_constructive TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT fk_thresholds_aspect FOREIGN KEY (aspect_id) REFERENCES aspects(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS intervention_rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  aspect_id INT NOT NULL UNIQUE,
  diagnosed_pattern VARCHAR(500) NOT NULL,
  recommendation TEXT NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT fk_rules_aspect FOREIGN KEY (aspect_id) REFERENCES aspects(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  aspect_id INT NOT NULL,
  department_id INT NULL,
  negative_count INT NOT NULL,
  constructive_count INT NOT NULL DEFAULT 0,
  diagnosed_pattern TEXT,
  recommendation TEXT NOT NULL,
  status ENUM('new', 'acknowledged', 'in-progress', 'resolved') NOT NULL DEFAULT 'new',
  note TEXT,
  quad_note TEXT NULL,
  confirmed_at DATETIME NULL,
  completed_at DATETIME NULL,
  completion_note TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_alerts_aspect FOREIGN KEY (aspect_id) REFERENCES aspects(id),
  CONSTRAINT fk_alerts_department FOREIGN KEY (department_id) REFERENCES departments(id),
  INDEX idx_alerts_status (status)
) ENGINE=InnoDB;
