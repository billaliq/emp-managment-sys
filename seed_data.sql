-- ============================================================
-- EMS Dummy Data — paste into Supabase SQL Editor and Run All
-- ============================================================

-- Departments
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Information Technology', 'Software development and IT support', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Human Resources', 'Recruitment and employee relations', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Finance and Accounts', 'Financial planning and accounting', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Marketing', 'Brand management and digital marketing', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Operations', 'Day-to-day business operations', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_department" (name, description, status, created_at, updated_at, use_custom_timings) VALUES ('Sales', 'Client acquisition and revenue', 'active', NOW(), NOW(), false) ON CONFLICT (name) DO NOTHING;

-- Positions
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Software Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Senior Software Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Junior Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Frontend Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Backend Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Full Stack Developer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('QA Engineer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('DevOps Engineer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('UI/UX Designer', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Project Manager', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Business Analyst', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('HR Executive', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Accountant', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Finance Manager', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Marketing Manager', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('Sales Executive', 'active', NOW()) ON CONFLICT (name) DO NOTHING;
INSERT INTO "EMSwebsite_position" (name, status, date_added) VALUES ('System Administrator', 'active', NOW()) ON CONFLICT (name) DO NOTHING;

-- Employees (50 records)
DO $$
DECLARE
  dept_ids  int[];
  pos_ids   int[];
BEGIN
  SELECT array_agg(id) INTO dept_ids FROM "EMSwebsite_department" WHERE status = 'active';
  SELECT array_agg(id) INTO pos_ids  FROM "EMSwebsite_position"   WHERE status = 'active';

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1001', 'Imran', 'Ahmed', 'Rashid Khan', '20480-5520673-7',
     'Male', 'Married', 'AB-', '1999-06-13',
     '03202061273', '03226192507', '03351222103', 'Yasir Chaudhry',
     'imran.ahmed1001@gmail.com', 'imran.ahmed@aliq.tech', 'House 172, Street 69, Sector C, Rawalpindi', 'House 151, Street 84, Sector A, Rawalpindi',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Faisal',
     dept_ids[1 + (0 % array_length(dept_ids,1))],
     pos_ids[1 + (0  % array_length(pos_ids,1))],
     'Project Manager', 'Saeed Malik',
     '2023-06-14', 156707, 'Faysal Bank', 'Gulshan Branch',
     'Imran Ahmed', '86424555550', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1002', 'Amina', 'Qureshi', 'Mohsin Mirza', '84958-7884094-3',
     'Female', 'Single', 'A+', '1987-12-15',
     '03233454937', '03353018514', '03487038631', 'Imran Iqbal',
     'amina.qureshi1002@gmail.com', 'amina.qureshi@aliq.tech', 'House 496, Street 23, Sector C, Islamabad', 'House 264, Street 20, Sector E, Islamabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Zubair',
     dept_ids[1 + (1 % array_length(dept_ids,1))],
     pos_ids[1 + (1  % array_length(pos_ids,1))],
     'Senior Developer', 'Junaid Mirza',
     '2024-10-23', 159714, 'Allied Bank', 'Main Branch',
     'Amina Qureshi', '80348673678', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1003', 'Sobia', 'Siddiqui', 'Yasir Qureshi', '96181-9784128-8',
     'Female', 'Married', 'O-', '1989-11-15',
     '03475108211', '03272444039', '03202416276', 'Omar Rashid',
     'sobia.siddiqui1003@gmail.com', 'sobia.siddiqui@aliq.tech', 'House 159, Street 93, Sector D, Faisalabad', 'House 403, Street 94, Sector F, Faisalabad',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Zubair',
     dept_ids[1 + (2 % array_length(dept_ids,1))],
     pos_ids[1 + (2  % array_length(pos_ids,1))],
     'HR Executive', 'Nadeem Iqbal',
     '2024-05-10', 242191, 'Allied Bank', 'Model Town Branch',
     'Sobia Siddiqui', '53454111223', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1004', 'Zainab', 'Siddiqui', 'Junaid Sheikh', '67179-3745081-5',
     'Female', 'Single', 'O-', '1990-10-20',
     '03237920586', '03438550726', '03229630451', 'Yasir Hussain',
     'zainab.siddiqui1004@gmail.com', 'zainab.siddiqui@aliq.tech', 'House 55, Street 16, Sector E, Rawalpindi', 'House 81, Street 19, Sector E, Rawalpindi',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Govinda',
     dept_ids[1 + (3 % array_length(dept_ids,1))],
     pos_ids[1 + (3  % array_length(pos_ids,1))],
     'Accountant', 'Imran Siddiqui',
     '2024-02-05', 208937, 'Faysal Bank', 'Main Branch',
     'Zainab Siddiqui', '17089524732', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1005', 'Uzma', 'Sheikh', 'Hassan Ali', '38400-3397790-1',
     'Female', 'Married', 'A+', '2000-01-30',
     '03415565911', '03115295013', '03406384506', 'Junaid Qureshi',
     'uzma.sheikh1005@gmail.com', 'uzma.sheikh@aliq.tech', 'House 121, Street 2, Sector D, Karachi', 'House 320, Street 39, Sector B, Karachi',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Govinda',
     dept_ids[1 + (4 % array_length(dept_ids,1))],
     pos_ids[1 + (4  % array_length(pos_ids,1))],
     'DevOps Engineer', 'Ali Khan',
     '2024-06-13', 161642, 'Meezan Bank', 'Main Branch',
     'Uzma Sheikh', '56707811823', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1006', 'Bilal', 'Butt', 'Ibrahim Raza', '38347-1679338-3',
     'Male', 'Single', 'B+', '2004-01-23',
     '03314363259', '03483715453', '03239784101', 'Usman Ahmed',
     'bilal.butt1006@gmail.com', 'bilal.butt@aliq.tech', 'House 164, Street 10, Sector E, Karachi', 'House 130, Street 94, Sector D, Karachi',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Zubair',
     dept_ids[1 + (5 % array_length(dept_ids,1))],
     pos_ids[1 + (5  % array_length(pos_ids,1))],
     'Sales Executive', 'Bilal Mirza',
     '2025-07-12', 113237, 'HBL', 'Model Town Branch',
     'Bilal Butt', '19850572592', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1007', 'Tariq', 'Raza', 'Qasim Iqbal', '27526-7140481-6',
     'Male', 'Married', 'B-', '1995-08-02',
     '03439667899', '03435486461', '03457577327', 'Nadeem Mirza',
     'tariq.raza1007@gmail.com', 'tariq.raza@aliq.tech', 'House 429, Street 5, Sector D, Rawalpindi', 'House 93, Street 2, Sector C, Rawalpindi',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Accounts',
     dept_ids[1 + (6 % array_length(dept_ids,1))],
     pos_ids[1 + (6  % array_length(pos_ids,1))],
     'Senior Developer', 'Bilal Qureshi',
     '2023-11-18', 196772, 'Bank Alfalah', 'Gulshan Branch',
     'Tariq Raza', '40866207052', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1008', 'Kiran', 'Siddiqui', 'Tariq Raza', '60147-4875745-4',
     'Female', 'Single', 'A+', '1989-07-20',
     '03339965504', '03387868706', '03363547088', 'Saeed Mirza',
     'kiran.siddiqui1008@gmail.com', 'kiran.siddiqui@aliq.tech', 'House 257, Street 70, Sector B, Rawalpindi', 'House 69, Street 71, Sector B, Rawalpindi',
     'EB''s Technology', 'Remote', 'Part Time', 'HR',
     dept_ids[1 + (7 % array_length(dept_ids,1))],
     pos_ids[1 + (7  % array_length(pos_ids,1))],
     'Backend Developer', 'Omar Butt',
     '2025-01-24', 228993, 'UBL', 'DHA Branch',
     'Kiran Siddiqui', '48907940621', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1009', 'Yasir', 'Shah', 'Mohsin Chaudhry', '36111-6874805-6',
     'Male', 'Married', 'A-', '1987-10-30',
     '03352558720', '03334552268', '03432571360', 'Usman Chaudhry',
     'yasir.shah1009@gmail.com', 'yasir.shah@aliq.tech', 'House 222, Street 28, Sector C, Karachi', 'House 265, Street 4, Sector E, Karachi',
     'EB''s Technology', 'Onsite', 'Part Time', 'Accounts',
     dept_ids[1 + (8 % array_length(dept_ids,1))],
     pos_ids[1 + (8  % array_length(pos_ids,1))],
     'QA Engineer', 'Muhammad Siddiqui',
     '2024-10-08', 180070, 'Meezan Bank', 'Main Branch',
     'Yasir Shah', '51568479837', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1010', 'Shazia', 'Raza', 'Hassan Siddiqui', '70132-8312349-1',
     'Female', 'Married', 'AB-', '1988-06-19',
     '03428373652', '03254236997', '03492568932', 'Junaid Hassan',
     'shazia.raza1010@gmail.com', 'shazia.raza@aliq.tech', 'House 33, Street 30, Sector D, Faisalabad', 'House 455, Street 94, Sector A, Faisalabad',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Faisal',
     dept_ids[1 + (9 % array_length(dept_ids,1))],
     pos_ids[1 + (9  % array_length(pos_ids,1))],
     'DevOps Engineer', 'Hussain Ali',
     '2025-09-07', 86137, 'Meezan Bank', 'DHA Branch',
     'Shazia Raza', '37902400675', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1011', 'Uzma', 'Mirza', 'Zubair Khan', '64384-5858569-6',
     'Female', 'Single', 'O-', '1999-04-18',
     '03265981838', '03385506459', '03352178686', 'Saeed Sheikh',
     'uzma.mirza1011@gmail.com', 'uzma.mirza@aliq.tech', 'House 190, Street 75, Sector C, Faisalabad', 'House 39, Street 7, Sector E, Faisalabad',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Faisal',
     dept_ids[1 + (10 % array_length(dept_ids,1))],
     pos_ids[1 + (10  % array_length(pos_ids,1))],
     'Finance Manager', 'Nadeem Hussain',
     '2024-10-26', 204481, 'HBL', 'Gulshan Branch',
     'Uzma Mirza', '28310614608', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1012', 'Bilal', 'Malik', 'Hassan Mirza', '75639-5612460-5',
     'Male', 'Married', 'B-', '1999-11-23',
     '03124614479', '03284363141', '03197357989', 'Tariq Ali',
     'bilal.malik1012@gmail.com', 'bilal.malik@aliq.tech', 'House 265, Street 92, Sector A, Rawalpindi', 'House 434, Street 11, Sector B, Rawalpindi',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Suhail',
     dept_ids[1 + (11 % array_length(dept_ids,1))],
     pos_ids[1 + (11  % array_length(pos_ids,1))],
     'Accountant', 'Usman Malik',
     '2025-01-22', 91904, 'Allied Bank', 'Main Branch',
     'Bilal Malik', '88410583046', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1013', 'Qasim', 'Butt', 'Usman Butt', '33074-9992714-9',
     'Male', 'Married', 'AB-', '2002-03-10',
     '03236754153', '03423000692', '03212099737', 'Faisal Rashid',
     'qasim.butt1013@gmail.com', 'qasim.butt@aliq.tech', 'House 36, Street 82, Sector A, Islamabad', 'House 51, Street 54, Sector B, Islamabad',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (12 % array_length(dept_ids,1))],
     pos_ids[1 + (12  % array_length(pos_ids,1))],
     'Marketing Manager', 'Usman Sheikh',
     '2025-01-03', 76420, 'MCB', 'Gulshan Branch',
     'Qasim Butt', '53009260585', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1014', 'Sobia', 'Rashid', 'Yasir Qureshi', '94727-5487800-2',
     'Female', 'Married', 'A-', '1995-03-27',
     '03139368088', '03411778562', '03222165313', 'Bilal Rashid',
     'sobia.rashid1014@gmail.com', 'sobia.rashid@aliq.tech', 'House 420, Street 71, Sector E, Faisalabad', 'House 250, Street 42, Sector E, Faisalabad',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Sir Govinda',
     dept_ids[1 + (13 % array_length(dept_ids,1))],
     pos_ids[1 + (13  % array_length(pos_ids,1))],
     'QA Engineer', 'Nadeem Khan',
     '2024-11-17', 65134, 'Meezan Bank', 'Main Branch',
     'Sobia Rashid', '45141918540', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1015', 'Mohsin', 'Siddiqui', 'Junaid Shah', '30277-5349147-5',
     'Male', 'Married', 'B-', '1986-11-24',
     '03312579774', '03162061459', '03199742973', 'Usman Chaudhry',
     'mohsin.siddiqui1015@gmail.com', 'mohsin.siddiqui@aliq.tech', 'House 271, Street 28, Sector C, Islamabad', 'House 200, Street 90, Sector D, Islamabad',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Zubair',
     dept_ids[1 + (14 % array_length(dept_ids,1))],
     pos_ids[1 + (14  % array_length(pos_ids,1))],
     'Sales Executive', 'Imran Hassan',
     '2023-12-25', 97642, 'Allied Bank', 'Gulshan Branch',
     'Mohsin Siddiqui', '96262586627', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1016', 'Muhammad', 'Malik', 'Kamran Butt', '62025-4709304-3',
     'Male', 'Single', 'A+', '1999-07-14',
     '03241039401', '03393028509', '03456800397', 'Omar Malik',
     'muhammad.malik1016@gmail.com', 'muhammad.malik@aliq.tech', 'House 342, Street 97, Sector B, Karachi', 'House 488, Street 23, Sector A, Karachi',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Faisal',
     dept_ids[1 + (15 % array_length(dept_ids,1))],
     pos_ids[1 + (15  % array_length(pos_ids,1))],
     'DevOps Engineer', 'Zain Sheikh',
     '2025-11-02', 155017, 'Faysal Bank', 'Main Branch',
     'Muhammad Malik', '27985043720', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1017', 'Muhammad', 'Hassan', 'Kamran Iqbal', '36520-6038424-1',
     'Male', 'Single', 'AB+', '1987-05-03',
     '03206230160', '03188633487', '03365297662', 'Bilal Raza',
     'muhammad.hassan1017@gmail.com', 'muhammad.hassan@aliq.tech', 'House 265, Street 56, Sector B, Rawalpindi', 'House 5, Street 19, Sector D, Rawalpindi',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (16 % array_length(dept_ids,1))],
     pos_ids[1 + (16  % array_length(pos_ids,1))],
     'Finance Manager', 'Imran Siddiqui',
     '2025-03-08', 140854, 'UBL', 'Model Town Branch',
     'Muhammad Hassan', '75236038127', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1018', 'Sara', 'Malik', 'Omar Hassan', '81795-2231110-4',
     'Female', 'Married', 'A+', '1997-06-16',
     '03195331139', '03268756447', '03419965240', 'Mohsin Raza',
     'sara.malik1018@gmail.com', 'sara.malik@aliq.tech', 'House 432, Street 22, Sector E, Lahore', 'House 463, Street 58, Sector E, Lahore',
     'EB''s Technology', 'Remote', 'Part Time', 'Accounts',
     dept_ids[1 + (17 % array_length(dept_ids,1))],
     pos_ids[1 + (17  % array_length(pos_ids,1))],
     'Senior Developer', 'Kamran Chaudhry',
     '2025-03-09', 214321, 'Meezan Bank', 'DHA Branch',
     'Sara Malik', '48844479555', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1019', 'Sara', 'Ahmed', 'Omar Hassan', '39142-9068690-1',
     'Female', 'Single', 'AB+', '1994-06-10',
     '03417930264', '03385336702', '03454027091', 'Qasim Malik',
     'sara.ahmed1019@gmail.com', 'sara.ahmed@aliq.tech', 'House 421, Street 9, Sector E, Lahore', 'House 339, Street 33, Sector F, Lahore',
     'EB''s Technology', 'Remote', 'Full Time', 'HR',
     dept_ids[1 + (18 % array_length(dept_ids,1))],
     pos_ids[1 + (18  % array_length(pos_ids,1))],
     'QA Engineer', 'Omar Chaudhry',
     '2025-07-05', 152694, 'HBL', 'Gulshan Branch',
     'Sara Ahmed', '76091928110', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1020', 'Iqra', 'Chaudhry', 'Qasim Siddiqui', '65781-3795594-6',
     'Female', 'Single', 'B+', '1987-09-09',
     '03197815984', '03372589967', '03157711729', 'Mohsin Ali',
     'iqra.chaudhry1020@gmail.com', 'iqra.chaudhry@aliq.tech', 'House 90, Street 48, Sector E, Faisalabad', 'House 304, Street 70, Sector D, Faisalabad',
     'EB''s Technology', 'Onsite', 'Part Time', 'Accounts',
     dept_ids[1 + (19 % array_length(dept_ids,1))],
     pos_ids[1 + (19  % array_length(pos_ids,1))],
     'Project Manager', 'Hassan Ali',
     '2024-06-06', 238790, 'Allied Bank', 'Main Branch',
     'Iqra Chaudhry', '97623140365', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1021', 'Bilal', 'Hussain', 'Faisal Butt', '28594-6603464-5',
     'Male', 'Single', 'AB+', '2004-05-15',
     '03279212990', '03175685744', '03417162133', 'Yasir Qureshi',
     'bilal.hussain1021@gmail.com', 'bilal.hussain@aliq.tech', 'House 97, Street 19, Sector A, Faisalabad', 'House 403, Street 82, Sector D, Faisalabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Faisal',
     dept_ids[1 + (20 % array_length(dept_ids,1))],
     pos_ids[1 + (20  % array_length(pos_ids,1))],
     'Accountant', 'Yasir Malik',
     '2026-02-10', 42570, 'Bank Alfalah', 'Model Town Branch',
     'Bilal Hussain', '84600293223', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1022', 'Zubair', 'Hassan', 'Nadeem Ahmed', '67056-1515220-2',
     'Male', 'Single', 'B+', '2000-08-12',
     '03435515650', '03297307351', '03374892402', 'Bilal Ahmed',
     'zubair.hassan1022@gmail.com', 'zubair.hassan@aliq.tech', 'House 271, Street 9, Sector E, Lahore', 'House 301, Street 24, Sector F, Lahore',
     'EB''s Technology', 'Remote', 'Part Time', 'HR',
     dept_ids[1 + (21 % array_length(dept_ids,1))],
     pos_ids[1 + (21  % array_length(pos_ids,1))],
     'Project Manager', 'Qasim Hussain',
     '2025-07-23', 244694, 'Allied Bank', 'DHA Branch',
     'Zubair Hassan', '38880054795', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1023', 'Farah', 'Ahmed', 'Ali Malik', '14668-3240167-9',
     'Female', 'Married', 'AB-', '2001-08-06',
     '03445969068', '03152988050', '03355678466', 'Hamza Khan',
     'farah.ahmed1023@gmail.com', 'farah.ahmed@aliq.tech', 'House 268, Street 28, Sector D, Faisalabad', 'House 233, Street 81, Sector B, Faisalabad',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Sir Faisal',
     dept_ids[1 + (22 % array_length(dept_ids,1))],
     pos_ids[1 + (22  % array_length(pos_ids,1))],
     'QA Engineer', 'Ali Mirza',
     '2025-04-25', 219007, 'UBL', 'Main Branch',
     'Farah Ahmed', '40200733367', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1024', 'Fatima', 'Mirza', 'Qasim Khan', '85083-7668631-7',
     'Female', 'Married', 'AB-', '1992-07-13',
     '03118694594', '03498278286', '03487510742', 'Junaid Iqbal',
     'fatima.mirza1024@gmail.com', 'fatima.mirza@aliq.tech', 'House 42, Street 51, Sector B, Lahore', 'House 31, Street 19, Sector D, Lahore',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Govinda',
     dept_ids[1 + (23 % array_length(dept_ids,1))],
     pos_ids[1 + (23  % array_length(pos_ids,1))],
     'Software Developer', 'Junaid Hassan',
     '2024-03-25', 224167, 'Meezan Bank', 'Main Branch',
     'Fatima Mirza', '13209385816', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1025', 'Maria', 'Rashid', 'Zubair Hussain', '83255-4342764-9',
     'Female', 'Married', 'A-', '1993-04-13',
     '03215396859', '03158231171', '03156553633', 'Hamza Rashid',
     'maria.rashid1025@gmail.com', 'maria.rashid@aliq.tech', 'House 73, Street 74, Sector B, Islamabad', 'House 147, Street 17, Sector A, Islamabad',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (24 % array_length(dept_ids,1))],
     pos_ids[1 + (24  % array_length(pos_ids,1))],
     'Backend Developer', 'Ali Shah',
     '2024-04-07', 126970, 'UBL', 'DHA Branch',
     'Maria Rashid', '31474568486', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1026', 'Maria', 'Rashid', 'Zubair Malik', '71311-8146188-5',
     'Female', 'Single', 'B+', '2001-05-28',
     '03302249385', '03479686214', '03156844585', 'Saeed Iqbal',
     'maria.rashid1026@gmail.com', 'maria.rashid@aliq.tech', 'House 71, Street 74, Sector C, Islamabad', 'House 160, Street 55, Sector D, Islamabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'Accounts',
     dept_ids[1 + (25 % array_length(dept_ids,1))],
     pos_ids[1 + (25  % array_length(pos_ids,1))],
     'HR Executive', 'Ahmed Hussain',
     '2023-06-15', 201218, 'Bank Alfalah', 'Model Town Branch',
     'Maria Rashid', '81943195547', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1027', 'Qasim', 'Ahmed', 'Omar Chaudhry', '84148-8064621-2',
     'Male', 'Single', 'O+', '1997-03-08',
     '03182513764', '03103803226', '03303111867', 'Faisal Malik',
     'qasim.ahmed1027@gmail.com', 'qasim.ahmed@aliq.tech', 'House 439, Street 8, Sector B, Lahore', 'House 232, Street 67, Sector E, Lahore',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (26 % array_length(dept_ids,1))],
     pos_ids[1 + (26  % array_length(pos_ids,1))],
     'Accountant', 'Muhammad Sheikh',
     '2025-03-24', 204543, 'UBL', 'Model Town Branch',
     'Qasim Ahmed', '75463083315', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1028', 'Qasim', 'Rashid', 'Tariq Shah', '91785-1245946-7',
     'Male', 'Married', 'A-', '1997-10-02',
     '03162002709', '03429623830', '03358583177', 'Faisal Ahmed',
     'qasim.rashid1028@gmail.com', 'qasim.rashid@aliq.tech', 'House 394, Street 23, Sector A, Lahore', 'House 78, Street 30, Sector F, Lahore',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (27 % array_length(dept_ids,1))],
     pos_ids[1 + (27  % array_length(pos_ids,1))],
     'Sales Executive', 'Bilal Sheikh',
     '2024-05-17', 53086, 'UBL', 'Model Town Branch',
     'Qasim Rashid', '69791934117', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1029', 'Tahira', 'Butt', 'Bilal Rashid', '76604-5895463-5',
     'Female', 'Single', 'A+', '1993-07-16',
     '03385107239', '03127782311', '03415591236', 'Usman Sheikh',
     'tahira.butt1029@gmail.com', 'tahira.butt@aliq.tech', 'House 24, Street 30, Sector F, Islamabad', 'House 344, Street 46, Sector A, Islamabad',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Govinda',
     dept_ids[1 + (28 % array_length(dept_ids,1))],
     pos_ids[1 + (28  % array_length(pos_ids,1))],
     'QA Engineer', 'Imran Iqbal',
     '2025-06-28', 102245, 'MCB', 'Model Town Branch',
     'Tahira Butt', '32336607244', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1030', 'Bilal', 'Malik', 'Bilal Malik', '69488-2060180-8',
     'Male', 'Single', 'A-', '1991-06-14',
     '03287241109', '03455987388', '03163384116', 'Waseem Iqbal',
     'bilal.malik1030@gmail.com', 'bilal.malik@aliq.tech', 'House 70, Street 2, Sector B, Islamabad', 'House 387, Street 96, Sector E, Islamabad',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Sir Zubair',
     dept_ids[1 + (29 % array_length(dept_ids,1))],
     pos_ids[1 + (29  % array_length(pos_ids,1))],
     'QA Engineer', 'Kamran Sheikh',
     '2023-07-19', 246128, 'Bank Alfalah', 'Main Branch',
     'Bilal Malik', '32382676553', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1031', 'Zain', 'Rashid', 'Omar Shah', '41298-1415297-4',
     'Male', 'Single', 'AB+', '1988-01-22',
     '03233032569', '03316789517', '03129382148', 'Junaid Chaudhry',
     'zain.rashid1031@gmail.com', 'zain.rashid@aliq.tech', 'House 21, Street 49, Sector E, Faisalabad', 'House 200, Street 29, Sector F, Faisalabad',
     'EB''s Technology', 'Hybrid', 'Part Time', 'HR',
     dept_ids[1 + (30 % array_length(dept_ids,1))],
     pos_ids[1 + (30  % array_length(pos_ids,1))],
     'Backend Developer', 'Muhammad Hussain',
     '2024-05-16', 233740, 'Bank Alfalah', 'DHA Branch',
     'Zain Rashid', '87659665627', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1032', 'Usman', 'Malik', 'Bilal Hussain', '45105-9143097-1',
     'Male', 'Married', 'A+', '1988-07-07',
     '03413199222', '03495942008', '03498066882', 'Ali Khan',
     'usman.malik1032@gmail.com', 'usman.malik@aliq.tech', 'House 171, Street 37, Sector E, Rawalpindi', 'House 189, Street 94, Sector F, Rawalpindi',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Govinda',
     dept_ids[1 + (31 % array_length(dept_ids,1))],
     pos_ids[1 + (31  % array_length(pos_ids,1))],
     'HR Executive', 'Imran Raza',
     '2025-02-28', 115058, 'Faysal Bank', 'DHA Branch',
     'Usman Malik', '53684746099', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1033', 'Shazia', 'Siddiqui', 'Waseem Qureshi', '23930-3971225-6',
     'Female', 'Married', 'B-', '2003-03-05',
     '03103582536', '03308921108', '03138053138', 'Qasim Hussain',
     'shazia.siddiqui1033@gmail.com', 'shazia.siddiqui@aliq.tech', 'House 331, Street 21, Sector E, Rawalpindi', 'House 226, Street 37, Sector C, Rawalpindi',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (32 % array_length(dept_ids,1))],
     pos_ids[1 + (32  % array_length(pos_ids,1))],
     'Project Manager', 'Ali Ahmed',
     '2024-06-07', 210300, 'Allied Bank', 'Main Branch',
     'Shazia Siddiqui', '90576482794', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1034', 'Hussain', 'Raza', 'Yasir Khan', '21779-7703552-8',
     'Male', 'Married', 'B+', '1990-12-07',
     '03129729028', '03496597023', '03131521705', 'Tariq Ali',
     'hussain.raza1034@gmail.com', 'hussain.raza@aliq.tech', 'House 192, Street 87, Sector F, Rawalpindi', 'House 12, Street 83, Sector B, Rawalpindi',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Govinda',
     dept_ids[1 + (33 % array_length(dept_ids,1))],
     pos_ids[1 + (33  % array_length(pos_ids,1))],
     'Sales Executive', 'Hassan Rashid',
     '2024-08-01', 67335, 'HBL', 'DHA Branch',
     'Hussain Raza', '81972878483', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1035', 'Fatima', 'Rashid', 'Ahmed Mirza', '67870-9990001-9',
     'Female', 'Single', 'A-', '1991-01-28',
     '03261556988', '03471406701', '03342903757', 'Yasir Ahmed',
     'fatima.rashid1035@gmail.com', 'fatima.rashid@aliq.tech', 'House 120, Street 45, Sector A, Faisalabad', 'House 384, Street 23, Sector D, Faisalabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Govinda',
     dept_ids[1 + (34 % array_length(dept_ids,1))],
     pos_ids[1 + (34  % array_length(pos_ids,1))],
     'Sales Executive', 'Imran Malik',
     '2024-10-19', 164197, 'Bank Alfalah', 'Gulshan Branch',
     'Fatima Rashid', '61578294874', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1036', 'Maria', 'Malik', 'Hamza Siddiqui', '31879-4488647-6',
     'Female', 'Married', 'B-', '1999-01-07',
     '03408432785', '03296492679', '03243402890', 'Faisal Siddiqui',
     'maria.malik1036@gmail.com', 'maria.malik@aliq.tech', 'House 41, Street 20, Sector C, Lahore', 'House 288, Street 28, Sector D, Lahore',
     'EB''s Technology', 'Remote', 'Full Time', 'Sir Govinda',
     dept_ids[1 + (35 % array_length(dept_ids,1))],
     pos_ids[1 + (35  % array_length(pos_ids,1))],
     'Finance Manager', 'Omar Shah',
     '2024-09-03', 56662, 'Faysal Bank', 'DHA Branch',
     'Maria Malik', '19376177190', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1037', 'Fatima', 'Chaudhry', 'Hussain Ahmed', '43404-1089429-9',
     'Female', 'Single', 'B+', '1994-08-05',
     '03127179454', '03442284963', '03186442901', 'Bilal Chaudhry',
     'fatima.chaudhry1037@gmail.com', 'fatima.chaudhry@aliq.tech', 'House 407, Street 26, Sector B, Islamabad', 'House 183, Street 70, Sector A, Islamabad',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (36 % array_length(dept_ids,1))],
     pos_ids[1 + (36  % array_length(pos_ids,1))],
     'Accountant', 'Zubair Malik',
     '2025-11-10', 222728, 'Meezan Bank', 'Main Branch',
     'Fatima Chaudhry', '42652587242', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1038', 'Faisal', 'Siddiqui', 'Ahmed Hassan', '13492-7300328-2',
     'Male', 'Single', 'B+', '1998-11-09',
     '03403395713', '03259358612', '03184906358', 'Hassan Raza',
     'faisal.siddiqui1038@gmail.com', 'faisal.siddiqui@aliq.tech', 'House 72, Street 100, Sector B, Faisalabad', 'House 173, Street 2, Sector A, Faisalabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Faisal',
     dept_ids[1 + (37 % array_length(dept_ids,1))],
     pos_ids[1 + (37  % array_length(pos_ids,1))],
     'Senior Developer', 'Ahmed Raza',
     '2023-12-10', 195803, 'HBL', 'DHA Branch',
     'Faisal Siddiqui', '80793189064', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1039', 'Kamran', 'Mirza', 'Imran Qureshi', '56966-1928313-2',
     'Male', 'Married', 'AB-', '1993-06-01',
     '03331260472', '03221006436', '03301863335', 'Omar Mirza',
     'kamran.mirza1039@gmail.com', 'kamran.mirza@aliq.tech', 'House 437, Street 54, Sector F, Lahore', 'House 177, Street 89, Sector B, Lahore',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Suhail',
     dept_ids[1 + (38 % array_length(dept_ids,1))],
     pos_ids[1 + (38  % array_length(pos_ids,1))],
     'QA Engineer', 'Hamza Ali',
     '2024-01-20', 107873, 'Faysal Bank', 'Gulshan Branch',
     'Kamran Mirza', '24824112250', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1040', 'Sara', 'Shah', 'Zain Sheikh', '40034-3943802-3',
     'Female', 'Married', 'B-', '2000-03-04',
     '03485473398', '03262546371', '03307344609', 'Tariq Iqbal',
     'sara.shah1040@gmail.com', 'sara.shah@aliq.tech', 'House 92, Street 39, Sector B, Karachi', 'House 494, Street 7, Sector C, Karachi',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Faisal',
     dept_ids[1 + (39 % array_length(dept_ids,1))],
     pos_ids[1 + (39  % array_length(pos_ids,1))],
     'Accountant', 'Ali Chaudhry',
     '2025-11-28', 200305, 'Meezan Bank', 'Model Town Branch',
     'Sara Shah', '73287444307', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1041', 'Tariq', 'Hussain', 'Qasim Raza', '13063-2666084-7',
     'Male', 'Single', 'B-', '2004-02-18',
     '03324293796', '03348923819', '03308751207', 'Tariq Siddiqui',
     'tariq.hussain1041@gmail.com', 'tariq.hussain@aliq.tech', 'House 132, Street 62, Sector B, Rawalpindi', 'House 497, Street 47, Sector E, Rawalpindi',
     'EB''s Technology', 'Onsite', 'Part Time', 'HR',
     dept_ids[1 + (40 % array_length(dept_ids,1))],
     pos_ids[1 + (40  % array_length(pos_ids,1))],
     'Accountant', 'Zain Ali',
     '2024-06-22', 177894, 'Meezan Bank', 'Main Branch',
     'Tariq Hussain', '37325984771', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1042', 'Hassan', 'Mirza', 'Mohsin Raza', '10771-3997769-5',
     'Male', 'Married', 'B+', '1996-07-29',
     '03208530173', '03222523083', '03103352959', 'Mohsin Shah',
     'hassan.mirza1042@gmail.com', 'hassan.mirza@aliq.tech', 'House 369, Street 62, Sector B, Islamabad', 'House 331, Street 15, Sector C, Islamabad',
     'EB''s Technology', 'Onsite', 'Full Time', 'HR',
     dept_ids[1 + (41 % array_length(dept_ids,1))],
     pos_ids[1 + (41  % array_length(pos_ids,1))],
     'Backend Developer', 'Zubair Butt',
     '2024-05-04', 127165, 'Meezan Bank', 'Gulshan Branch',
     'Hassan Mirza', '49138009385', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1043', 'Zubair', 'Malik', 'Saeed Sheikh', '71641-9096216-3',
     'Male', 'Married', 'AB-', '2003-06-15',
     '03497555556', '03398707345', '03331637655', 'Omar Chaudhry',
     'zubair.malik1043@gmail.com', 'zubair.malik@aliq.tech', 'House 373, Street 22, Sector E, Karachi', 'House 253, Street 81, Sector F, Karachi',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Accounts',
     dept_ids[1 + (42 % array_length(dept_ids,1))],
     pos_ids[1 + (42  % array_length(pos_ids,1))],
     'Sales Executive', 'Ahmed Raza',
     '2024-03-12', 192170, 'Meezan Bank', 'Gulshan Branch',
     'Zubair Malik', '65985346805', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1044', 'Hamza', 'Hassan', 'Kamran Siddiqui', '68278-8665717-7',
     'Male', 'Married', 'A-', '1991-11-02',
     '03206387595', '03348728815', '03219858136', 'Muhammad Iqbal',
     'hamza.hassan1044@gmail.com', 'hamza.hassan@aliq.tech', 'House 268, Street 34, Sector C, Faisalabad', 'House 36, Street 25, Sector B, Faisalabad',
     'EB''s Technology', 'Hybrid', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (43 % array_length(dept_ids,1))],
     pos_ids[1 + (43  % array_length(pos_ids,1))],
     'Backend Developer', 'Omar Hassan',
     '2023-05-21', 201507, 'Allied Bank', 'DHA Branch',
     'Hamza Hassan', '25847529672', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1045', 'Zain', 'Butt', 'Rashid Malik', '43301-5656499-6',
     'Male', 'Married', 'B-', '1990-04-06',
     '03187749775', '03276707673', '03123891209', 'Ahmed Hassan',
     'zain.butt1045@gmail.com', 'zain.butt@aliq.tech', 'House 111, Street 35, Sector B, Lahore', 'House 51, Street 98, Sector B, Lahore',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Zubair',
     dept_ids[1 + (44 % array_length(dept_ids,1))],
     pos_ids[1 + (44  % array_length(pos_ids,1))],
     'Senior Developer', 'Hussain Butt',
     '2025-08-29', 124367, 'MCB', 'DHA Branch',
     'Zain Butt', '10914413475', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1046', 'Hamza', 'Butt', 'Muhammad Raza', '77961-7728076-8',
     'Male', 'Married', 'O-', '1989-02-15',
     '03184572165', '03177173349', '03326310368', 'Omar Hussain',
     'hamza.butt1046@gmail.com', 'hamza.butt@aliq.tech', 'House 76, Street 98, Sector A, Lahore', 'House 355, Street 55, Sector E, Lahore',
     'EB''s Technology', 'Onsite', 'Full Time', 'Sir Suhail',
     dept_ids[1 + (45 % array_length(dept_ids,1))],
     pos_ids[1 + (45  % array_length(pos_ids,1))],
     'Sales Executive', 'Yasir Rashid',
     '2024-06-29', 44484, 'Bank Alfalah', 'Gulshan Branch',
     'Hamza Butt', '74458805695', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1047', 'Ibrahim', 'Shah', 'Mohsin Hassan', '97908-3103263-2',
     'Male', 'Single', 'B+', '2000-10-21',
     '03225773761', '03414498696', '03258351379', 'Saeed Rashid',
     'ibrahim.shah1047@gmail.com', 'ibrahim.shah@aliq.tech', 'House 468, Street 18, Sector A, Islamabad', 'House 94, Street 23, Sector D, Islamabad',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Accounts',
     dept_ids[1 + (46 % array_length(dept_ids,1))],
     pos_ids[1 + (46  % array_length(pos_ids,1))],
     'Accountant', 'Saeed Khan',
     '2023-06-15', 69472, 'Bank Alfalah', 'Model Town Branch',
     'Ibrahim Shah', '87021961467', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1048', 'Uzma', 'Chaudhry', 'Waseem Siddiqui', '20821-8304850-2',
     'Female', 'Single', 'AB-', '1995-01-31',
     '03452435337', '03186279170', '03268880927', 'Hussain Siddiqui',
     'uzma.chaudhry1048@gmail.com', 'uzma.chaudhry@aliq.tech', 'House 211, Street 98, Sector A, Karachi', 'House 479, Street 94, Sector A, Karachi',
     'EB''s Technology', 'Hybrid', 'Full Time', 'Accounts',
     dept_ids[1 + (47 % array_length(dept_ids,1))],
     pos_ids[1 + (47  % array_length(pos_ids,1))],
     'Marketing Manager', 'Saeed Qureshi',
     '2023-12-29', 98101, 'Faysal Bank', 'DHA Branch',
     'Uzma Chaudhry', '59592020747', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1049', 'Waseem', 'Hassan', 'Mohsin Sheikh', '76013-3633542-5',
     'Male', 'Single', 'AB+', '1996-06-08',
     '03427416284', '03434485761', '03298883431', 'Yasir Rashid',
     'waseem.hassan1049@gmail.com', 'waseem.hassan@aliq.tech', 'House 49, Street 78, Sector C, Lahore', 'House 112, Street 44, Sector B, Lahore',
     'EB''s Technology', 'Onsite', 'Part Time', 'Sir Zubair',
     dept_ids[1 + (48 % array_length(dept_ids,1))],
     pos_ids[1 + (48  % array_length(pos_ids,1))],
     'Sales Executive', 'Tariq Rashid',
     '2023-07-06', 88190, 'Faysal Bank', 'Gulshan Branch',
     'Waseem Hassan', '46155168988', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO "EMSwebsite_employees"
    (code, firstname, lastname, father_name, national_id,
     gender, marital_status, blood_group, dob,
     contact_1, contact_2, emergency_contact, emergency_contact_person,
     email, official_email, present_address, permanent_address,
     location, work_mode, employment_type, team,
     department_id, position_id, job_title, reporting_to,
     date_hired, salary, bank_name, branch_name,
     account_title, account_number, status,
     date_added, date_updated, profile_submitted, increment_cycle_months)
  VALUES
    ('1050', 'Zainab', 'Ahmed', 'Hamza Ali', '62406-5831870-5',
     'Female', 'Single', 'A-', '1986-12-01',
     '03387155709', '03273677368', '03482900916', 'Rashid Khan',
     'zainab.ahmed1050@gmail.com', 'zainab.ahmed@aliq.tech', 'House 250, Street 67, Sector B, Islamabad', 'House 127, Street 98, Sector F, Islamabad',
     'EB''s Technology', 'Remote', 'Part Time', 'Sir Suhail',
     dept_ids[1 + (49 % array_length(dept_ids,1))],
     pos_ids[1 + (49  % array_length(pos_ids,1))],
     'Software Developer', 'Yasir Butt',
     '2024-08-15', 54485, 'UBL', 'Gulshan Branch',
     'Zainab Ahmed', '10906250309', 1,
     NOW(), NOW(), false, 6)
  ON CONFLICT (code) DO NOTHING;

END $$;

-- Attendance records (last 30 weekdays per employee)
DO $$
DECLARE
  emp RECORD;
  att_date date;
BEGIN
  FOR emp IN SELECT id, date_hired FROM "EMSwebsite_employees"
             WHERE code = ANY(ARRAY['1001','1002','1003','1004','1005','1006','1007','1008','1009','1010','1011','1012','1013','1014','1015','1016','1017','1018','1019','1020','1021','1022','1023','1024','1025','1026','1027','1028','1029','1030','1031','1032','1033','1034','1035','1036','1037','1038','1039','1040','1041','1042','1043','1044','1045','1046','1047','1048','1049','1050']) LOOP

    att_date := DATE '2026-04-20';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, NULL, NULL,
         'absent', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-21';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:07:00', '19:09:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-22';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '08:45:00', '20:45:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-23';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, NULL, NULL,
         'absent', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-24';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '08:48:00', '20:35:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-27';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:12:00', '18:48:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-28';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:29:00', '17:38:00',
         'late', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-29';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '08:47:00', '19:01:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-04-30';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:54:00', '18:29:00',
         'late', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-01';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:02:00', '18:57:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-04';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:12:00', '20:27:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-05';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '08:53:00', '18:10:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-06';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:09:00', '19:35:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-07';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '10:12:00', '17:36:00',
         'late', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-08';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, NULL, NULL,
         'leave', 'sick', 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-11';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:13:00', '20:24:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-12';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:03:00', '18:03:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-13';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:23:00', '18:59:00',
         'late', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-14';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '08:57:00', '19:50:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
    att_date := DATE '2026-05-15';
    IF att_date >= emp.date_hired THEN
      INSERT INTO "EMSwebsite_attendance"
        (employee_id, date, check_in_time, check_out_time,
         status, leave_type, overtime_hours, created_at, updated_at)
      VALUES
        (emp.id, att_date, '09:13:00', '20:13:00',
         'present', NULL, 0.00, NOW(), NOW())
      ON CONFLICT (employee_id, date) DO NOTHING;
    END IF;
  END LOOP;
END $$;

-- Verify
SELECT 'Employees' AS table_name, COUNT(*) FROM "EMSwebsite_employees"
UNION ALL
SELECT 'Departments', COUNT(*) FROM "EMSwebsite_department"
UNION ALL
SELECT 'Positions',   COUNT(*) FROM "EMSwebsite_position"
UNION ALL
SELECT 'Attendance',  COUNT(*) FROM "EMSwebsite_attendance";