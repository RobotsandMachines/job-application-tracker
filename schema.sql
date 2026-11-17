DROP DATABASE IF EXISTS job_tracker_project;
CREATE DATABASE job_tracker_project;
USE job_tracker_project;

CREATE TABLE IF NOT EXISTS companies (
    company_id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(100) NOT NULL,
    industry VARCHAR(50),
    website VARCHAR(200),
    city VARCHAR(50),
    state VARCHAR(50),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id INT PRIMARY KEY AUTO_INCREMENT,
    company_id INT,
    job_title VARCHAR(100) NOT NULL,
    job_type ENUM('Full-time','Part-time','Contract','Internship'),
    salary_min INT,
    salary_max INT,
    job_url VARCHAR(300),
    date_posted DATE,
    requirements JSON,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    application_id INT PRIMARY KEY AUTO_INCREMENT,
    job_id INT,
    application_date DATE NOT NULL,
    status ENUM('Applied','Screening','Interview','Offer','Rejected','Withdrawn'),
    resume_version VARCHAR(50),
    cover_letter_sent BOOLEAN,
    interview_data JSON,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contacts (
    contact_id INT PRIMARY KEY AUTO_INCREMENT,
    company_id INT,
    contact_name VARCHAR(100) NOT NULL,
    title VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    linkedin_url VARCHAR(200),
    notes TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- Random Made Up Sample data mixed with real data
INSERT INTO companies (company_name, industry, website, city, state, notes) VALUES
('Hextronics', 'Software', 'https://hextronics.com/', 'Miami', 'FL', 'Fast-growing startup'),
('Ford', 'Automotive', 'https://www.ford.com', 'Dearborn', 'MI', NULL),
('Procter and Gamble', 'Consumer Goods', 'https://www.pg.com', 'Cincinnati', 'OH', NULL),
('Southwest Airlines', 'Airlines', 'https://www.southwest.com', 'Dallas', 'TX', NULL),
('Bradesco Bank', 'Banking', 'https://www.bradesco.com.br', 'Osasco', 'São Paulo', 'Headquartered in Brazil');

INSERT INTO jobs (company_id, job_title, job_type, salary_min, salary_max, job_url, date_posted, requirements) VALUES
(1, 'Software Developer', 'Full-time', 75000, 95000, 'https://techcorp.com/jobs/1', '2026-11-01', '["Python", "SQL", "Flask"]'),
(2, 'Data Analyst', 'Full-time', 65000, 80000, 'https://dataco.com/jobs/2', '2026-11-03', '["Python", "SQL", "Tableau"]'),
(3, 'Cloud Engineer Intern', 'Internship', 25000, 30000, 'https://cloudnine.io/jobs/3', '2026-10-28', '["AWS", "Linux", "Python"]'),
(4, 'Security Analyst', 'Full-time', 70000, 90000, 'https://securenet.com/jobs/4', '2026-11-05', '["Networking", "Linux", "SIEM", "Python"]'),
(5, 'Frontend Developer', 'Contract', 50000, 70000, 'https://webworks.dev/jobs/5', '2026-11-02', '["HTML", "CSS", "JavaScript"]'),
(1, 'Backend Developer', 'Full-time', 80000, 100000, 'https://techcorp.com/jobs/6', '2026-11-08', '["Python", "Flask", "MySQL", "Docker"]'),
(2, 'Database Administrator', 'Part-time', 40000, 55000, 'https://dataco.com/jobs/7', '2026-10-30', '["SQL", "MySQL", "Linux"]');

INSERT INTO applications (job_id, application_date, status, resume_version, cover_letter_sent, interview_data) VALUES
(1, '2026-11-04', 'Interview', 'v2', TRUE, '{"round": 1, "interviewer": "Jane Smith", "notes": "Technical screen went well"}'),
(2, '2026-11-05', 'Applied', 'v2', FALSE, NULL),
(4, '2026-11-07', 'Screening', 'v3-security', TRUE, '{"round": 0, "notes": "Recruiter call scheduled"}'),
(5, '2026-11-03', 'Rejected', 'v1', FALSE, NULL),
(6, '2026-11-09', 'Offer', 'v2', TRUE, '{"round": 3, "interviewer": "Mark Lee", "notes": "Offer received"}'),
(7, '2026-11-11', 'Withdrawn', 'v3-security', TRUE, NULL);

INSERT INTO contacts (company_id, contact_name, title, email, phone, linkedin_url, notes) VALUES
(1, 'Jane Smith', 'Engineering Manager', 'jane@techcorp.com', '305-555-0101', 'https://linkedin.com/in/janesmith', 'Met at career fair'),
(2, 'Carlos Ruiz', 'Recruiter', 'carlos@dataco.com', '407-555-0102', 'https://linkedin.com/in/carlosruiz', NULL),
(4, 'Aisha Khan', 'Security Lead', 'aisha@securenet.com', '813-555-0103', 'https://linkedin.com/in/aishakhan', 'Referred by professor'),
(1, 'Mark Lee', 'CTO', 'mark@techcorp.com', '305-555-0104', NULL, 'Final round interviewer'),
(5, 'Emily Chen', 'HR Coordinator', 'emily@webworks.dev', '404-555-0105', 'https://linkedin.com/in/emilychen', NULL);