"""
Generates seed_data.sql  — paste that file into Supabase SQL Editor and run it.
Usage:  python seed_data.py
"""
import random, os
from datetime import date, timedelta, time

today = date.today()

MALE   = ['Ahmed','Ali','Bilal','Hassan','Hussain','Ibrahim','Imran','Kamran',
          'Muhammad','Nadeem','Omar','Qasim','Rashid','Saeed','Tariq','Usman',
          'Waseem','Yasir','Zain','Zubair','Faisal','Hamza','Junaid','Mohsin']
FEMALE = ['Ayesha','Fatima','Hina','Kiran','Maria','Nida','Rabia','Sana','Sara',
          'Shazia','Sobia','Tahira','Uzma','Zainab','Amina','Farah','Hira','Iqra']
LASTS  = ['Ahmed','Ali','Khan','Malik','Hassan','Hussain','Iqbal','Raza','Shah',
          'Sheikh','Butt','Chaudhry','Mirza','Qureshi','Rashid','Siddiqui']
BANKS  = ['HBL','UBL','MCB','Allied Bank','Bank Alfalah','Meezan Bank','Faysal Bank']
TEAMS  = ['Sir Faisal','Sir Zubair','Sir Govinda','Sir Suhail','HR','Accounts']
WMODES = ['Onsite','Remote','Hybrid']
ETYPES = ['Full Time','Part Time']
BLOODS = ['A+','A-','B+','B-','O+','O-','AB+','AB-']
CITIES = ['Karachi','Lahore','Islamabad','Rawalpindi','Faisalabad']
JOBS   = ['Software Developer','Senior Developer','Frontend Developer','Backend Developer',
          'QA Engineer','DevOps Engineer','UI/UX Designer','Project Manager',
          'HR Executive','Accountant','Finance Manager','Marketing Manager','Sales Executive']
DEPTS  = [
    ('Information Technology', 'Software development and IT support'),
    ('Human Resources',        'Recruitment and employee relations'),
    ('Finance and Accounts',   'Financial planning and accounting'),
    ('Marketing',              'Brand management and digital marketing'),
    ('Operations',             'Day-to-day business operations'),
    ('Sales',                  'Client acquisition and revenue'),
]
POSITIONS = [
    'Software Developer','Senior Software Developer','Junior Developer',
    'Frontend Developer','Backend Developer','Full Stack Developer',
    'QA Engineer','DevOps Engineer','UI/UX Designer','Project Manager',
    'Business Analyst','HR Executive','Accountant','Finance Manager',
    'Marketing Manager','Sales Executive','System Administrator',
]
ATT_W  = ['present']*65 + ['late']*15 + ['absent']*10 + ['early-out']*5 + ['leave']*5
LEAVES = ['sick','personal','annual','casual']

def esc(s):
    return str(s).replace("'", "''")

def phone():
    return f"03{random.randint(10,49)}{random.randint(1000000,9999999)}"

def cnic():
    return f"{random.randint(10000,99999)}-{random.randint(1000000,9999999)}-{random.randint(1,9)}"

def addr(city):
    sectors = ['A','B','C','D','E','F']
    return f"House {random.randint(1,500)}, Street {random.randint(1,100)}, Sector {random.choice(sectors)}, {city}"

lines = []
lines.append("-- ============================================================")
lines.append("-- EMS Dummy Data — paste into Supabase SQL Editor and Run All")
lines.append("-- ============================================================")
lines.append("")

# ── Departments ───────────────────────────────────────────────────────────────
lines.append("-- Departments")
for name, desc in DEPTS:
    lines.append(
        f"INSERT INTO \"EMSwebsite_department\" "
        f"(name, description, status, created_at, updated_at, use_custom_timings) "
        f"VALUES ('{esc(name)}', '{esc(desc)}', 'active', NOW(), NOW(), false) "
        f"ON CONFLICT (name) DO NOTHING;"
    )
lines.append("")

# ── Positions ─────────────────────────────────────────────────────────────────
lines.append("-- Positions")
for p in POSITIONS:
    lines.append(
        f"INSERT INTO \"EMSwebsite_position\" (name, status, date_added) "
        f"VALUES ('{esc(p)}', 'active', NOW()) "
        f"ON CONFLICT (name) DO NOTHING;"
    )
lines.append("")

# ── Employees ─────────────────────────────────────────────────────────────────
lines.append("-- Employees (50 records)")
lines.append("DO $$")
lines.append("DECLARE")
lines.append("  dept_ids  int[];")
lines.append("  pos_ids   int[];")
lines.append("BEGIN")
lines.append("  SELECT array_agg(id) INTO dept_ids FROM \"EMSwebsite_department\" WHERE status = 'active';")
lines.append("  SELECT array_agg(id) INTO pos_ids  FROM \"EMSwebsite_position\"   WHERE status = 'active';")
lines.append("")

used_codes = set()
emp_data   = []   # (code, firstname, lastname, hired_date) for attendance

for i in range(50):
    code = 1001 + i
    while str(code) in used_codes:
        code += 1
    used_codes.add(str(code))

    gender    = random.choice(['Male', 'Female'])
    firstname = random.choice(MALE if gender == 'Male' else FEMALE)
    lastname  = random.choice(LASTS)
    city      = random.choice(CITIES)
    dob       = today - timedelta(days=random.randint(8030, 14600))
    hired     = today - timedelta(days=random.randint(60, 1095))
    salary    = random.randint(35000, 250000)
    bank      = random.choice(BANKS)
    branch    = random.choice(['Main','Gulshan','DHA','Model Town']) + ' Branch'
    team      = random.choice(TEAMS)
    wmode     = random.choice(WMODES)
    etype     = random.choice(ETYPES)
    blood     = random.choice(BLOODS)
    marital   = random.choice(['Single','Married'])
    job       = random.choice(JOBS)
    father    = f"{random.choice(MALE)} {random.choice(LASTS)}"
    reporting = f"{random.choice(MALE)} {random.choice(LASTS)}"
    email     = f"{firstname.lower()}.{lastname.lower()}{code}@gmail.com"
    off_email = f"{firstname.lower()}.{lastname.lower()}@aliq.tech"
    p_addr    = addr(city)
    perm_addr = addr(city)
    acc_num   = str(random.randint(10_000_000_000, 99_999_999_999))
    ph1       = phone()
    ph2       = phone()
    em_ph     = phone()
    em_person = f"{random.choice(MALE)} {random.choice(LASTS)}"
    nat_id    = cnic()

    emp_data.append((str(code), firstname, lastname, hired))

    lines.append(f"  INSERT INTO \"EMSwebsite_employees\"")
    lines.append(f"    (code, firstname, lastname, father_name, national_id,")
    lines.append(f"     gender, marital_status, blood_group, dob,")
    lines.append(f"     contact_1, contact_2, emergency_contact, emergency_contact_person,")
    lines.append(f"     email, official_email, present_address, permanent_address,")
    lines.append(f"     location, work_mode, employment_type, team,")
    lines.append(f"     department_id, position_id, job_title, reporting_to,")
    lines.append(f"     date_hired, salary, bank_name, branch_name,")
    lines.append(f"     account_title, account_number, status,")
    lines.append(f"     date_added, date_updated, profile_submitted, increment_cycle_months)")
    lines.append(f"  VALUES")
    lines.append(f"    ('{code}', '{esc(firstname)}', '{esc(lastname)}', '{esc(father)}', '{nat_id}',")
    lines.append(f"     '{gender}', '{marital}', '{blood}', '{dob}',")
    lines.append(f"     '{ph1}', '{ph2}', '{em_ph}', '{esc(em_person)}',")
    lines.append(f"     '{esc(email)}', '{esc(off_email)}', '{esc(p_addr)}', '{esc(perm_addr)}',")
    lines.append(f"     'EB''s Technology', '{wmode}', '{etype}', '{esc(team)}',")
    lines.append(f"     dept_ids[1 + ({i} % array_length(dept_ids,1))],")
    lines.append(f"     pos_ids[1 + ({i}  % array_length(pos_ids,1))],")
    lines.append(f"     '{esc(job)}', '{esc(reporting)}',")
    lines.append(f"     '{hired}', {salary}, '{bank}', '{branch}',")
    lines.append(f"     '{esc(firstname)} {esc(lastname)}', '{acc_num}', 1,")
    lines.append(f"     NOW(), NOW(), false, 6)")
    lines.append(f"  ON CONFLICT (code) DO NOTHING;")
    lines.append("")

lines.append("END $$;")
lines.append("")

# ── Attendance ────────────────────────────────────────────────────────────────
lines.append("-- Attendance records (last 30 weekdays per employee)")
lines.append("DO $$")
lines.append("DECLARE")
lines.append("  emp RECORD;")
lines.append("  att_date date;")
lines.append("BEGIN")
lines.append("  FOR emp IN SELECT id, date_hired FROM \"EMSwebsite_employees\"")
lines.append("             WHERE code = ANY(ARRAY[" +
             ",".join(f"'{c}'" for c,_,_,_ in emp_data) + "]) LOOP")
lines.append("")

for days_ago in range(30, 0, -1):
    att_date = today - timedelta(days=days_ago)
    if att_date.weekday() >= 5:   # skip weekends
        continue

    status = random.choice(ATT_W)
    ci = co = lt = 'NULL'

    if status == 'absent':
        st = 'absent'
    elif status == 'leave':
        lt_val = random.choice(LEAVES)
        lt = f"'{lt_val}'"
        st = 'leave'
    elif status == 'late':
        mins = random.randint(20, 90)
        h = 9 + mins // 60
        m = mins % 60
        ci = f"'{h:02d}:{m:02d}:00'"
        co = f"'{random.randint(17,19):02d}:{random.randint(0,59):02d}:00'"
        st = 'late'
    elif status == 'early-out':
        ci = f"'09:{random.randint(0,14):02d}:00'"
        co = f"'{random.randint(14,17):02d}:{random.randint(0,59):02d}:00'"
        st = 'early-out'
    else:
        h_in = 8 if random.random() < 0.3 else 9
        m_in = random.randint(45,59) if h_in == 8 else random.randint(0,14)
        ci = f"'{h_in:02d}:{m_in:02d}:00'"
        co = f"'{random.randint(18,20):02d}:{random.randint(0,59):02d}:00'"
        st = 'present'

    lines.append(f"    att_date := DATE '{att_date}';")
    lines.append(f"    IF att_date >= emp.date_hired THEN")
    lines.append(f"      INSERT INTO \"EMSwebsite_attendance\"")
    lines.append(f"        (employee_id, date, check_in_time, check_out_time,")
    lines.append(f"         status, leave_type, overtime_hours, created_at, updated_at)")
    lines.append(f"      VALUES")
    lines.append(f"        (emp.id, att_date, {ci}, {co},")
    lines.append(f"         '{st}', {lt}, 0.00, NOW(), NOW())")
    lines.append(f"      ON CONFLICT (employee_id, date) DO NOTHING;")
    lines.append(f"    END IF;")

lines.append("  END LOOP;")
lines.append("END $$;")
lines.append("")
lines.append("-- Verify")
lines.append("SELECT 'Employees' AS table_name, COUNT(*) FROM \"EMSwebsite_employees\"")
lines.append("UNION ALL")
lines.append("SELECT 'Departments', COUNT(*) FROM \"EMSwebsite_department\"")
lines.append("UNION ALL")
lines.append("SELECT 'Positions',   COUNT(*) FROM \"EMSwebsite_position\"")
lines.append("UNION ALL")
lines.append("SELECT 'Attendance',  COUNT(*) FROM \"EMSwebsite_attendance\";")

sql = "\n".join(lines)
out = os.path.join(os.path.dirname(__file__), "seed_data.sql")
with open(out, "w", encoding="utf-8") as f:
    f.write(sql)

print(f"Generated: {out}")
print(f"Open Supabase SQL Editor, paste the file contents, and click Run All.")
