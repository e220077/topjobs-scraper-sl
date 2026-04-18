import psycopg2
import os
import time
from scraper import get_vacancy_image, analyze_job_with_gemini

# DB Configuration (Pooler)
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

def repair():
    print("\n--- Starting Database Repair (Link Normalization Edition) ---")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT id, title, job_link FROM job_listings WHERE contact_email IS NULL;")
        broken_jobs = cur.fetchall()
        
        if not broken_jobs:
            print("No jobs missing emails. Everything looks good!")
            return

        print(f"Found {len(broken_jobs)} jobs missing emails. Fixing links and Analyzing...")
        
        for job_id, title, link in broken_jobs:
            print(f"\n[ID {job_id}] {title}")
            
            # FIX: Normalize the link before fetching
            if 'JobAdvertismentServlet' in link and '/applicant/' in link:
                normalized_link = 'https://www.topjobs.lk/employer/' + link.split('JobAdvertismentServlet')[-1]
                print(f"   - Normalized Link: {normalized_link}")
            else:
                normalized_link = link
                
            # Step 1: Detect Image
            image_url = get_vacancy_image(normalized_link)
            print(f"   - Detected Image: {image_url}")
            
            if not image_url:
                print("   - FAILED: Still no advertisement image found.")
                continue

            # Step 2: Gemini Analysis
            print(f"   - Sending to Gemini AI...")
            email, ai_desc = analyze_job_with_gemini(image_url, title)
            
            if email:
                cur.execute("UPDATE job_listings SET contact_email = %s, job_description = %s, job_link = %s WHERE id = %s", (email, ai_desc, normalized_link, job_id))
                conn.commit()
                print(f"   - SUCCESS! Found Email: {email}")
            else:
                print("   - FAILED: Gemini could not find an email in this image.")
            
            time.sleep(2)
                
        cur.close()
        conn.close()
        print("\n--- Repair process completed ---")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    repair()
