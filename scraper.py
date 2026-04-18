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

# Configuration
# Scan both Software Development and general IT categories to avoid missing jobs
CATEGORIES = ["SDQ", "IT"]
URL_TEMPLATE = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA={}"
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.topjobs.lk/'
}

# Expanded skills to include variations found in images (Spring, JEE)
TARGET_SKILLS = ['Spring Boot', 'Spring Batch', 'Spring', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'React', 'Angular', 'Java', 'JEE', 'Python', 'PostgreSQL', 'MySQL', 'MongoDB', 'REST', 'GraphQL']

# Words that indicate a job is definitely NOT what we want
FORBIDDEN_TITLES = ['Relationship', 'Sales', 'Accountant', 'Marketing', 'Customer', 'Steward', 'Chef', 'Driver', 'Pharmacy']

def save_job(job_data):
    sql = """INSERT INTO job_listings(title, company, job_link, image_url, job_description)
             VALUES(%s, %s, %s, %s, %s) ON CONFLICT (job_link) DO NOTHING;"""
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(sql, (job_data['title'], job_data['company'], job_data['link'], job_data['image_url'], job_data['job_description']))
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

def process_single_job(tr, alert_pattern):
    try:
        onclick_content = tr.get('onclick', '')
        match = alert_pattern.search(onclick_content)
        if not match: return None
        
        i, ac, jc, ec, _id = match.groups()
        job_link = f"../employer/JobAdvertismentServlet?rid={i}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
        
        tds = tr.find_all('td')
        if len(tds) < 3: return False
        
        company_name = tds[1].get_text(strip=True)
        job_title = tds[2].get_text(strip=True)
        
        if any(f.lower() in job_title.lower() for f in FORBIDDEN_TITLES):
            return False

        print(f"Checking: {job_title} at {company_name}")
        
        image_url, clean_description = get_clean_vacancy_content(job_link)
        
        text_match = False
        for skill in TARGET_SKILLS:
            if skill.lower() in clean_description.lower():
                text_match = True
                print(f"   -> Match found: {skill}")
                break
        
        if text_match:
            job_data = {
                'title': job_title,
                'company': company_name,
                'link': 'https://www.topjobs.lk/applicant/' + job_link.replace('../', ''),
                'image_url': image_url,
                'job_description': clean_description.strip()
            }
            save_job(job_data)
            return True
        return False
    except Exception:
        return False

def scrape_topjobs():
    print(f"Scraping TopJobs IT Categories (Clean Edition)...")
    total_match_count = 0
    
    for category in CATEGORIES:
        category_url = URL_TEMPLATE.format(category)
        print(f"\n--- Scanning Category: {category} ---")
        
        try:
            res = requests.get(category_url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            alert_pattern = re.compile(r"createAlert\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\)")
            job_rows = soup.find_all('tr', id=re.compile(r'tr\d+')) 
            
            if not job_rows:
                print(f"No jobs found in category {category}")
                continue
                
            print(f"Found {len(job_rows)} jobs. Scanning...")

            match_count = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(process_single_job, tr, alert_pattern) for tr in job_rows]
                for future in as_completed(futures):
                    if future.result(): match_count += 1
            
            total_match_count += match_count
            
        except Exception as e:
            print(f"Scraper Error in {category}: {e}")
            
    print(f"\nFinal Result: Found {total_match_count} engineering jobs matching your profile.")

if __name__ == "__main__":
    scrape_topjobs()
