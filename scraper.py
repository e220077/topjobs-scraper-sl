import requests
from bs4 import BeautifulSoup
import psycopg2
import time
import re
import os
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json
import urllib.parse

# Configuration
CATEGORIES = ["SDQ", "IT", "HNS"]
URL_TEMPLATE = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA={}"
DB_URL = os.getenv('DATABASE_URL')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
CV_PATH = "Dinal Maduranga.pdf"

model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.topjobs.lk/'
}

TARGET_SKILLS = ['Spring Boot', 'Spring Batch', 'Spring', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'React', 'Angular', 'Java', 'JEE', 'Python', 'PostgreSQL', 'MySQL', 'MongoDB', 'REST', 'GraphQL', 'SQL']
FORBIDDEN_TITLES = ['Relationship', 'Sales', 'Accountant', 'Marketing', 'Customer', 'Steward', 'Chef', 'Driver', 'Pharmacy', 'Restaurant', 'Waiter', 'Cashier', 'Hostess']
FORBIDDEN_SKILLS = ['.net', 'c#', 'php', 'laravel', 'flutter', 'ruby', 'c++', 'asp.net', 'golang', 'rust']
EMAIL_REGEX = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
TECH_HINT_REGEX = re.compile(r'\b(engineer|developer|software|backend|frontend|full\s*stack|qa|devops|cloud|it|data|security)\b', re.IGNORECASE)
JAVA_FALSE_POSITIVE_REGEX = re.compile(r'\bjava\s+(lounge|cafe|coffee|bistro|restaurant)\b', re.IGNORECASE)

TARGET_SKILL_PATTERNS = [
    ('Spring Boot', re.compile(r'\bspring\s*boot\b', re.IGNORECASE)),
    ('Spring Batch', re.compile(r'\bspring\s*batch\b', re.IGNORECASE)),
    ('Spring', re.compile(r'\bspring\b', re.IGNORECASE)),
    ('Node.js', re.compile(r'\bnode(?:\.js|\s*js)?\b', re.IGNORECASE)),
    ('AWS', re.compile(r'\baws\b', re.IGNORECASE)),
    ('Docker', re.compile(r'\bdocker\b', re.IGNORECASE)),
    ('Kubernetes', re.compile(r'\bkubernetes\b', re.IGNORECASE)),
    ('React', re.compile(r'\breact\b', re.IGNORECASE)),
    ('Angular', re.compile(r'\bangular\b', re.IGNORECASE)),
    ('Java', re.compile(r'\bjava\b', re.IGNORECASE)),
    ('JEE', re.compile(r'\bjee\b', re.IGNORECASE)),
    ('Python', re.compile(r'\bpython\b', re.IGNORECASE)),
    ('PostgreSQL', re.compile(r'\bpostgres(?:ql)?\b', re.IGNORECASE)),
    ('MySQL', re.compile(r'\bmysql\b', re.IGNORECASE)),
    ('MongoDB', re.compile(r'\bmongo(?:db)?\b', re.IGNORECASE)),
    ('REST', re.compile(r'\brest\b', re.IGNORECASE)),
    ('GraphQL', re.compile(r'\bgraphql\b', re.IGNORECASE)),
    ('SQL', re.compile(r'\bsql\b', re.IGNORECASE)),
]

ROLE_PATTERNS = [
    ('Software Engineer', re.compile(r'\bsoftware\s+engineer\b', re.IGNORECASE)),
    ('Software Developer', re.compile(r'\bsoftware\s+developer\b', re.IGNORECASE)),
    ('Full Stack', re.compile(r'\bfull[\s-]*stack\b', re.IGNORECASE)),
    ('Backend', re.compile(r'\bback[\s-]*end\b', re.IGNORECASE)),
    ('Frontend', re.compile(r'\bfront[\s-]*end\b', re.IGNORECASE)),
    ('Data Engineer', re.compile(r'\bdata\s+engineer\b', re.IGNORECASE)),
    ('DevOps', re.compile(r'\bdev[\s-]*ops\b', re.IGNORECASE)),
    ('QA Engineer', re.compile(r'\bqa\s+engineer\b', re.IGNORECASE)),
    ('Security Engineer', re.compile(r'\bsecurity\s+engineer\b', re.IGNORECASE)),
]

FORBIDDEN_SKILL_PATTERNS = [
    re.compile(r'(?<!\w)\.net\b', re.IGNORECASE),
    re.compile(r'\bc#\b', re.IGNORECASE),
    re.compile(r'\bphp\b', re.IGNORECASE),
    re.compile(r'\blaravel\b', re.IGNORECASE),
    re.compile(r'\bflutter\b', re.IGNORECASE),
    re.compile(r'\bruby\b', re.IGNORECASE),
    re.compile(r'c\+\+', re.IGNORECASE),
    re.compile(r'\basp\.net\b', re.IGNORECASE),
    re.compile(r'\bgolang\b', re.IGNORECASE),
    re.compile(r'\brust\b', re.IGNORECASE),
]

def get_missing_env_vars():
    required = ("DATABASE_URL", "GEMINI_API_KEY", "EMAIL_SENDER", "EMAIL_PASSWORD")
    return [key for key in required if not os.getenv(key)]

def normalize_skills(skills_value):
    if isinstance(skills_value, str):
        parts = re.split(r'[,;\n|/]+', skills_value)
    elif isinstance(skills_value, list):
        parts = skills_value
    else:
        return []

    normalized = []
    for part in parts:
        skill = str(part).strip()
        if skill:
            normalized.append(skill)
    return normalized

def dedupe_preserve_order(values):
    deduped = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped

def extract_target_skills(text):
    content = text or ""
    found = []
    for skill, pattern in TARGET_SKILL_PATTERNS:
        if not pattern.search(content):
            continue
        if skill == 'Java' and JAVA_FALSE_POSITIVE_REGEX.search(content):
            continue
        found.append(skill)
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(content):
            found.append(role)
    return dedupe_preserve_order(found)

def has_forbidden_skill(text):
    content = text or ""
    for pattern in FORBIDDEN_SKILL_PATTERNS:
        if pattern.search(content):
            return True
    return False

def should_use_ai_fallback(job_title, page_skills, page_email):
    if page_skills and page_email:
        return False
    if page_skills:
        return True
    return bool(TECH_HINT_REGEX.search(job_title or ""))

def parse_gemini_response(raw_text):
    clean_text = (raw_text or "").strip().replace('```json', '').replace('```', '').strip()
    email = None
    skills = []

    data = None
    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', clean_text)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None

    if isinstance(data, dict):
        email_value = data.get('email')
        if isinstance(email_value, str):
            email_candidate = email_value.strip().strip('.,;:')
            email = email_candidate or None
        skills = normalize_skills(data.get('skills', []))
    else:
        email_match = EMAIL_REGEX.search(clean_text)
        if email_match:
            email = email_match.group(0).strip('.,;:')

        skills_match = re.search(r'skills?\s*[:\-]\s*(.+)', clean_text, flags=re.IGNORECASE)
        if skills_match:
            skills = normalize_skills(skills_match.group(1))

    return email, ", ".join(skills)

def normalize_job_link(job_link):
    if 'JobAdvertismentServlet' in job_link and '/applicant/' in job_link:
        return 'https://www.topjobs.lk/employer/' + job_link.split('JobAdvertismentServlet')[-1]
    return job_link

def extract_contact_email(raw_html):
    emails = EMAIL_REGEX.findall(raw_html or "")
    seen = set()
    for email in emails:
        normalized = email.strip().strip('.,;:').lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if normalized.endswith('@topjobs.lk'):
            continue
        return normalized
    return None

def extract_visible_text(raw_html):
    soup = BeautifulSoup(raw_html or "", 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return " ".join(soup.stripped_strings)

def get_vacancy_page_details(job_link):
    job_link = normalize_job_link(job_link)
    res = requests.get(job_link, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, 'html.parser')
    page_email = extract_contact_email(res.text)
    page_text = extract_visible_text(res.text)

    images = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if any(junk in src.lower() for junk in ['info.png', 'local.jpg', 'loading.gif', 'application.png', '_small']):
            continue
        if '/vacancies/' in src or '/logo/' in src:
            full_src = src
            if not src.startswith('http'):
                full_src = 'https://www.topjobs.lk' + src if src.startswith('/') else 'https://www.topjobs.lk/employer/' + src
            images.append(full_src)

    image_url = None
    for img in images:
        if re.search(r'/logo/\d+/', img) or '/vacancies/' in img:
            image_url = img
            break
    if image_url is None and images:
        image_url = images[0]

    return image_url, page_email, page_text

def analyze_job_with_gemini(image_url, job_title):
    if not image_url or model is None:
        return None, ""
    try:
        encoded_url = urllib.parse.quote(image_url, safe=':/?&=')
        response = requests.get(encoded_url, headers=HEADERS, timeout=20)
        img = Image.open(BytesIO(response.content))
        prompt = f"Extract application info for: {job_title}\n1. email: Find the email address to apply to.\n2. skills: List key technical skills mentioned.\n\nReturn JSON ONLY: {{\"email\": \"...\", \"skills\": [\"...\", \"...\"]}}"
        ai_response = model.generate_content([prompt, img])
        return parse_gemini_response(ai_response.text)
    except Exception as e:
        print(f"   [AI Error] {e}")
        return None, ""

def save_job(job_data):
    if not DB_URL:
        print("DB Error: DATABASE_URL is not configured")
        return
    sql = """INSERT INTO job_listings(title, company, job_link, image_url, job_description, contact_email)
             VALUES(%s, %s, %s, %s, %s, %s) 
             ON CONFLICT (job_link) 
             DO UPDATE SET 
                contact_email = EXCLUDED.contact_email,
                job_description = EXCLUDED.job_description
             WHERE job_listings.contact_email IS NULL;"""
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(sql, (job_data['title'], job_data['company'], job_data['link'], job_data['image_url'], job_data['job_description'], job_data['contact_email']))
        conn.commit()
        cur.close()
    except Exception as error: print(f"DB Error: {error}")
    finally:
        if conn is not None: conn.close()

def get_vacancy_image(job_link, return_page_email=False):
    try:
        image, page_email, _page_text = get_vacancy_page_details(job_link)
        if return_page_email:
            return image, page_email
        return image
    except Exception:
        if return_page_email:
            return None, None
        return None

def send_application_email(to_email, job_title, company_name):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("   [Email Error]: EMAIL_SENDER/EMAIL_PASSWORD not configured")
        return False
    smtp_password = EMAIL_PASSWORD.replace(" ", "").strip()
    if not smtp_password:
        print("   [Email Error]: EMAIL_PASSWORD is empty after normalization")
        return False
    if not os.path.exists(CV_PATH): return False
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER.strip()
    msg['To'] = to_email
    msg['Subject'] = f"Application for {job_title} - Dinal Maduranga"
    body = f"Dear Hiring Manager at {company_name},\n\nI am writing to express my interest in the {job_title} position. Please find my CV attached.\n\nBest regards,\nDinal Maduranga"
    msg.attach(MIMEText(body, 'plain'))
    try:
        with open(CV_PATH, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(CV_PATH)}")
        msg.attach(part)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(msg['From'], smtp_password)
            server.sendmail(msg['From'], to_email, msg.as_string())
        print(f"   [Success] CV sent to {to_email}")
        return True
    except Exception as e: print(f"   [Email Error]: {e}"); return False

def process_single_job(tr, alert_pattern):
    try:
        onclick_content = tr.get('onclick', '')
        match = alert_pattern.search(onclick_content)
        if not match: return None
        i, ac, jc, ec, _id = match.groups()
        # FIXED: Use the correct root path
        job_link = f"https://www.topjobs.lk/employer/JobAdvertismentServlet?rid={i}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
        
        tds = tr.find_all('td')
        if len(tds) < 3: return False
        title_cell = tds[2]
        job_title = title_cell.find('h2').get_text(strip=True) if title_cell.find('h2') else "Untitled"
        company_name = title_cell.find('h1').get_text(strip=True) if title_cell.find('h1') else "Unknown"
        if any(f.lower() in job_title.lower() for f in FORBIDDEN_TITLES): return False

        print(f"AI Analyzing: {job_title} at {company_name}")
        image_url = None
        page_email = None
        page_text = ""
        try:
            image_url, page_email, page_text = get_vacancy_page_details(job_link)
        except Exception:
            image_url, page_email = get_vacancy_image(job_link, return_page_email=True)

        page_skills = extract_target_skills(f"{job_title} {page_text}")
        ai_email = None
        ai_description = ""
        ai_skills = []

        if should_use_ai_fallback(job_title, page_skills, page_email):
            ai_email, ai_description = analyze_job_with_gemini(image_url, job_title)
            ai_skills = extract_target_skills(ai_description)

        contact_email = page_email or ai_email
        matched_skills = dedupe_preserve_order(page_skills + ai_skills)

        combined_text = f"{job_title} {page_text} {ai_description}"
        if has_forbidden_skill(combined_text):
            return False

        if matched_skills:
            skill_description = ", ".join(matched_skills)
            if contact_email:
                print(f"   -> AI MATCH! Email: {contact_email}")
            else:
                print("   -> AI MATCH! Email not detected")
            save_job({
                'title': job_title, 'company': company_name, 'link': job_link,
                'image_url': image_url, 'job_description': skill_description, 'contact_email': contact_email
            })
            return True
        return False
    except Exception as e: return False

def auto_apply_jobs():
    print("\n--- Starting Auto-Apply Sequence ---")
    if not DB_URL:
        print("Auto-Apply Error: DATABASE_URL is not configured")
        return
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, title, company, contact_email FROM job_listings WHERE contact_email IS NOT NULL AND application_sent = FALSE;")
        pending_jobs = cur.fetchall()
        for job_id, title, company, email in pending_jobs:
            if send_application_email(email, title, company):
                cur.execute("UPDATE job_listings SET application_sent = TRUE WHERE id = %s;", (job_id,))
                conn.commit()
        cur.close()
    except Exception as e: print(f"Auto-Apply Error: {e}")
    finally:
        if conn is not None: conn.close()

def scrape_topjobs():
    print(f"Scraping TopJobs IT Categories (Clean Edition)...")
    for category in CATEGORIES:
        print(f"--- Category: {category} ---")
        try:
            res = requests.get(URL_TEMPLATE.format(category), headers=HEADERS, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            alert_pattern = re.compile(r"createAlert\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\)")
            job_rows = soup.find_all('tr', id=re.compile(r'tr\d+')) 
            with ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(lambda tr: process_single_job(tr, alert_pattern), job_rows))
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    missing = get_missing_env_vars()
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(1)
    scrape_topjobs()
    auto_apply_jobs()
