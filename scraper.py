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
URL = "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=IT"
# Use environment variable for database connection
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.topjobs.lk/'
}

# Key technologies to match
TARGET_SKILLS = ['Spring Boot', 'Spring Batch', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'React', 'Angular', 'Java', 'Python', 'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'REST', 'GraphQL']

def save_job(job_data):
    """
    Saves job record to Supabase PostgreSQL database.
    """
    sql = """INSERT INTO job_listings(title, company, job_link, image_url)
             VALUES(%s, %s, %s, %s) ON CONFLICT (job_link) DO NOTHING;"""
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(sql, (job_data['title'], job_data['company'], job_data['link'], job_data['image_url']))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"DB Error: {error}")
    finally:
        if conn is not None:
            conn.close()

def get_vacancy_data(job_link):
    """
    Crawls the vacancy detail page to find the advertisement image and page text.
    """
    try:
        if not job_link.startswith('http'):
            job_link = 'https://www.topjobs.lk/applicant/' + job_link.replace('../', '')
            
        res = requests.get(job_link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        image_url = None
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            if '/vacancies/' in src or '/logos/' in src:
                if not src.startswith('http'):
                    image_url = 'https://www.topjobs.lk' + src if src.startswith('/') else 'https://www.topjobs.lk/employer/' + src
                else:
                    image_url = src
                break
        
        page_text = soup.get_text()
        return image_url, page_text
    except Exception as e:
        print(f"Error fetching detail page {job_link}: {e}")
        return None, ""

def match_job_with_ocr(image_url):
    """
    Downloads image, performs OCR, and checks if any target skill is present.
    """
    if not image_url:
        return False
        
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=20)
        img = Image.open(BytesIO(response.content))
        
        # Perform OCR
        text = pytesseract.image_to_string(img).lower()
        
        for skill in TARGET_SKILLS:
            if skill.lower() in text:
                print(f"   [OCR Match] {skill}")
                return True
        return False
    except Exception as e:
        print(f"   OCR Error for {image_url}: {e}")
        return False

def process_single_job(tr, alert_pattern):
    """
    Worker function for multi-threaded processing.
    """
    try:
        onclick_content = tr.get('onclick', '')
        match = alert_pattern.search(onclick_content)
        if not match: return None
        
        i, ac, jc, ec, _id = match.groups()
        job_link = f"../employer/JobAdvertismentServlet?rid={i}&ac={ac}&jc={jc}&ec={ec}&pg=applicant/vacancybyfunctionalarea.jsp"
        
        company_name = "Unknown Company"
        job_title = "Untitled Position"
        tds = tr.find_all('td')
        if len(tds) > 2:
            texts = [td.get_text(strip=True) for td in tds if td.get_text(strip=True)]
            if len(texts) > 2:
                company_name = texts[1]
                job_title = texts[2]
        
        print(f"Checking: {job_title} at {company_name}")
        
        image_url, page_text = get_vacancy_data(job_link)
        
        # Check text first
        text_match = False
        for skill in TARGET_SKILLS:
            if skill.lower() in page_text.lower():
                text_match = True
                print(f"   [Text Match] {job_title}: {skill}")
                break
        
        # Then OCR
        if not text_match and image_url:
            text_match = match_job_with_ocr(image_url)
        
        if text_match:
            job_data = {
                'title': job_title,
                'company': company_name,
                'link': 'https://www.topjobs.lk/applicant/' + job_link.replace('../', ''),
                'image_url': image_url
            }
            save_job(job_data)
            return True
        return False
    except Exception as e:
        print(f"Worker Error: {e}")
        return False

def scrape_topjobs():
    print(f"Scraping TopJobs IT category (Cloud Edition)...")
    try:
        res = requests.get(URL, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        alert_pattern = re.compile(r"createAlert\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\)")
        job_rows = soup.find_all('tr', onclick=re.compile(r'createAlert'))
        
        match_count = 0
        print(f"Found {len(job_rows)} entries. Processing with parallel threads...")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_single_job, tr, alert_pattern) for tr in job_rows]
            for future in as_completed(futures):
                if future.result():
                    match_count += 1
            
        print(f"\nFinal Result: Found {match_count} jobs matching your profile.")
    except Exception as e:
        print(f"Scraper Error: {e}")

if __name__ == "__main__":
    scrape_topjobs()
