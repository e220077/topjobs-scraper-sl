import requests
from bs4 import BeautifulSoup
import psycopg2
import time
import re
import os
import pytesseract
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Configuration
CATEGORIES = ["SDQ", "IT", "HNS"]
URL_TEMPLATE = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA={}"
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

# Email Configuration for Auto-Apply
EMAIL_SENDER = os.getenv('EMAIL_SENDER', 'dnlmdrng@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '#Digital4491')
CV_PATH = "Dinal Maduranga.pdf"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.topjobs.lk/'
}

TARGET_SKILLS = ['Spring Boot', 'Spring Batch', 'Spring', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'React', 'Angular', 'Java', 'JEE', 'Python', 'PostgreSQL', 'MySQL', 'MongoDB', 'REST', 'GraphQL']
FORBIDDEN_TITLES = ['Relationship', 'Sales', 'Accountant', 'Marketing', 'Customer', 'Steward', 'Chef', 'Driver', 'Pharmacy']

def extract_email(text):
    """
    Finds email addresses in text using regex.
    """
    pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = re.findall(pattern, text)
    return emails[0] if emails else None

def save_job(job_data):
    sql = """INSERT INTO job_listings(title, company, job_link, image_url, job_description, contact_email)
             VALUES(%s, %s, %s, %s, %s, %s) ON CONFLICT (job_link) DO NOTHING;"""
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(sql, (job_data['title'], job_data['company'], job_data['link'], job_data['image_url'], job_data['job_description'], job_data['contact_email']))
        conn.commit()
        cur.close()
    except Exception as error:
        print(f"DB Error: {error}")
    finally:
        if conn is not None: conn.close()

def get_clean_vacancy_content(job_link):
    try:
        if not job_link.startswith('http'):
            job_link = 'https://www.topjobs.lk/applicant/' + job_link.replace('../', '')
            
        res = requests.get(job_link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        image_url = None
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            if '/vacancies/' in src or '/logo/' in src:
                if not src.startswith('http'):
                    image_url = 'https://www.topjobs.lk' + src if src.startswith('/') else 'https://www.topjobs.lk/employer/' + src
                else:
                    image_url = src
                break
        
        ocr_text = ""
        if image_url:
            try:
                img_res = requests.get(image_url, headers=HEADERS, timeout=15)
                img = Image.open(BytesIO(img_res.content))
                ocr_text = pytesseract.image_to_string(img)
            except:
                pass
                
        if not ocr_text:
            main_table = soup.find('table', class_='bx')
            if main_table:
                for sidebar in main_table.find_all(['ul', 'nav']): sidebar.decompose()
                ocr_text = main_table.get_text(separator=' ', strip=True)

        return image_url, ocr_text
    except Exception as e:
        print(f"Error fetching detail page: {e}")
        return None, ""

def send_application_email(to_email, job_title, company_name):
    """
    Sends application email with CV attached.
    """
    if not os.path.exists(CV_PATH):
        print(f"   [Error] CV not found at {CV_PATH}. Skipping application.")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = to_email
    msg['Subject'] = f"Application for {job_title} - Dinal Maduranga"

    body = f"""Dear Hiring Manager at {company_name},

I am writing to express my strong interest in the {job_title} position as advertised. 

With over 4 years of experience in Software Engineering, specializing in {', '.join(TARGET_SKILLS[:5])}, I am confident that my technical expertise and passion for building scalable applications make me an ideal candidate for your team.

Please find my CV attached for your review. I look forward to the possibility of discussing how my background can contribute to your organization.

Best regards,

Dinal Maduranga
+94 752 706 488
linkedin.com/in/mdinal
"""
    msg.attach(MIMEText(body, 'plain'))

    # Attach CV
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
        return True
    except Exception as e:
        print(f"   [Email Error] Failed to send to {to_email}: {e}")
        return False

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
        job_title = title_cell.find('h2').get_text(strip=True) if title_cell.find('h2') else "Untitled Position"
        company_name = title_cell.find('h1').get_text(strip=True) if title_cell.find('h1') else "Unknown Company"
        
        if any(f.lower() in job_title.lower() for f in FORBIDDEN_TITLES):
            return False

        image_url, clean_description = get_clean_vacancy_content(job_link)
        contact_email = extract_email(clean_description)
        
        search_blob = f"{job_title} {clean_description}".lower()
        text_match = False
        for skill in TARGET_SKILLS:
            if skill.lower() in search_blob:
                text_match = True
                break
        
        if text_match:
            print(f"Matched: {job_title} at {company_name} (Email: {contact_email})")
            job_data = {
                'title': job_title,
                'company': company_name,
                'link': 'https://www.topjobs.lk/applicant/' + job_link.replace('../', ''),
                'image_url': image_url,
                'job_description': clean_description.strip(),
                'contact_email': contact_email
            }
            save_job(job_data)
            return True
        return False
    except Exception:
        return False

def auto_apply_jobs():
    """
    Finds matching jobs in DB that haven't been applied to and sends CV.
    """
    print("\n--- Starting Auto-Apply Sequence ---")
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, title, company, contact_email FROM job_listings WHERE contact_email IS NOT NULL AND application_sent = FALSE;")
        pending_jobs = cur.fetchall()
        
        if not pending_jobs:
            print("No new jobs to apply for.")
            return

        print(f"Found {len(pending_jobs)} new jobs to apply for.")
        for job_id, title, company, email in pending_jobs:
            print(f"Applying to {title} at {company} ({email})...")
            if send_application_email(email, title, company):
                cur.execute("UPDATE job_listings SET application_sent = TRUE WHERE id = %s;", (job_id,))
                conn.commit()
                print("   [Success] Application sent.")
                time.sleep(2) # Be safe with SMTP
            else:
                print("   [Failed] Could not send email.")
                
        cur.close()
    except Exception as e:
        print(f"Auto-Apply Error: {e}")
    finally:
        if conn is not None: conn.close()

def scrape_topjobs():
    print(f"Scraping TopJobs IT Categories (Auto-Apply Edition)...")
    total_match_count = 0
    for category in CATEGORIES:
        category_url = URL_TEMPLATE.format(category)
        print(f"--- Scanning Category: {category} ---")
        try:
            res = requests.get(category_url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            alert_pattern = re.compile(r"createAlert\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\)")
            job_rows = soup.find_all('tr', id=re.compile(r'tr\d+')) 
            if not job_rows: continue
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(process_single_job, tr, alert_pattern) for tr in job_rows]
                for future in as_completed(futures):
                    if future.result(): total_match_count += 1
        except Exception as e:
            print(f"Scraper Error in {category}: {e}")
    print(f"\nScraping Finished. Found {total_match_count} new profile matches.")

if __name__ == "__main__":
    scrape_topjobs()
    auto_apply_jobs()
