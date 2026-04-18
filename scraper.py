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

# Configuration
CATEGORIES = ["SDQ", "IT", "HNS"]
URL_TEMPLATE = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA={}"
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAEP1ExvISZm17XzDxqy9BHmuYH9-viSYA')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

# Email Configuration for Auto-Apply
EMAIL_SENDER = os.getenv('EMAIL_SENDER', 'dnlmdrng@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '#Digital4491')
CV_PATH = "Dinal Maduranga.pdf"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.topjobs.lk/'
}

# Profile Alignment
TARGET_SKILLS = ['Spring Boot', 'Spring Batch', 'Spring', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'React', 'Angular', 'Java', 'JEE', 'Python', 'PostgreSQL', 'MySQL', 'MongoDB', 'REST', 'GraphQL', 'SQL']
FORBIDDEN_TITLES = ['Relationship', 'Sales', 'Accountant', 'Marketing', 'Customer', 'Steward', 'Chef', 'Driver', 'Pharmacy', 'Restaurant', 'Waiter', 'Cashier', 'Hostess']
FORBIDDEN_SKILLS = ['.net', 'c#', 'php', 'laravel', 'flutter', 'ruby', 'c++', 'asp.net', 'golang', 'rust']

def analyze_job_with_gemini(image_url, job_title):
    """
    Sends the job image to Gemini to extract email and technical skills.
    """
    if not image_url: return None, ""
    
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=20)
        img = Image.open(BytesIO(response.content))
        
        prompt = f"""
        Analyze this job advertisement image for the position: {job_title}.
        1. Extract the primary contact email address for applications.
        2. List all technical skills and technologies required.
        
        Return the result STRICTLY as a JSON object like this:
        {{"email": "careers@example.com", "skills": ["Java", "Spring"]}}
        If no email is found, set email to null.
        """
        
        ai_response = model.generate_content([prompt, img])
        data = json.loads(ai_response.text.strip(' `json\n'))
        return data.get('email'), ", ".join(data.get('skills', []))
    except Exception as e:
        print(f"   [Gemini Error] {e}")
        return None, ""

def save_job(job_data):
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

def get_vacancy_image(job_link):
    try:
        if not job_link.startswith('http'):
            job_link = 'https://www.topjobs.lk/applicant/' + job_link.replace('../', '')
        res = requests.get(job_link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            # Filter out known junk/system icons
            if any(junk in src.lower() for junk in ['info.png', 'local.jpg', 'loading.gif', 'application.png', '_small']):
                continue
                
            if '/vacancies/' in src or '/logo/' in src:
                full_src = src
                if not src.startswith('http'):
                    full_src = 'https://www.topjobs.lk' + src if src.startswith('/') else 'https://www.topjobs.lk/employer/' + src
                images.append(full_src)
        
        # PRIORITY LOGIC:
        # 1. Images with a numeric subdirectory (e.g., /logo/000000492/...) are usually the actual Ads
        for img in images:
            if re.search(r'/logo/\d+/', img) or '/vacancies/' in img:
                return img
        
        # 2. Fallback to the largest image found if no clear ad subdirectory
        return images[0] if images else None
    except: return None

def send_application_email(to_email, job_title, company_name):
    if not os.path.exists(CV_PATH): return False
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
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
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"   [Success] CV sent to {to_email}")
        return True
    except Exception as e: print(f"   [Email Error]: {e}"); return False

def process_single_job(tr, alert_pattern):
    try:
        onclick_content = tr.get('onclick', '')
        match = alert_pattern.search(onclick_content)
        if not match: return None
        i, ac, jc, ec, _id = match.groups()
        job_link = f"../employer/JobAdvertismentServlet?rid={i}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
        
        tds = tr.find_all('td')
        if len(tds) < 3: return False
        title_cell = tds[2]
        job_title = title_cell.find('h2').get_text(strip=True) if title_cell.find('h2') else "Untitled"
        company_name = title_cell.find('h1').get_text(strip=True) if title_cell.find('h1') else "Unknown"
        
        if any(f.lower() in job_title.lower() for f in FORBIDDEN_TITLES): return False

        print(f"AI Analyzing: {job_title} at {company_name}")
        image_url = get_vacancy_image(job_link)
        
        # USE GEMINI VISION
        contact_email, ai_description = analyze_job_with_gemini(image_url, job_title)
        
        search_blob = f"{job_title} {ai_description}".lower()
        if any(bad_skill.lower() in search_blob for bad_skill in FORBIDDEN_SKILLS): return False

        if any(skill.lower() in search_blob for skill in TARGET_SKILLS):
            print(f"   -> AI MATCH! Email: {contact_email}")
            save_job({
                'title': job_title, 'company': company_name, 'link': 'https://www.topjobs.lk/applicant/' + job_link.replace('../', ''),
                'image_url': image_url, 'job_description': ai_description, 'contact_email': contact_email
            })
            return True
        return False
    except Exception as e: print(f"Worker Error: {e}"); return False

def auto_apply_jobs():
    print("\n--- Starting Auto-Apply Sequence ---")
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
    print(f"Scraping TopJobs (Gemini AI Edition)...")
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
    scrape_topjobs()
    auto_apply_jobs()
