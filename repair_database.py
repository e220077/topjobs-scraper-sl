import psycopg2
import os
from scraper import get_vacancy_image, analyze_job_with_gemini

# DB Configuration (Pooler)
DB_URL = os.getenv('DATABASE_URL', 'postgresql://postgres.zqoypncilcortflwtpqg:cBAconAV0RtSxBDr@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres')

def repair():
    print("Starting Database Repair (Finding Missing Emails)...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Find all matched jobs that have no email
    cur.execute("SELECT id, title, job_link FROM job_listings WHERE contact_email IS NULL;")
    broken_jobs = cur.fetchall()
    
    if not broken_jobs:
        print("No broken jobs found. All entries have emails.")
        return

    print(f"Found {len(broken_jobs)} jobs missing emails. Re-scanning with Gemini...")
    
    for job_id, title, link in broken_jobs:
        print(f"Repairing ID {job_id}: {title}")
        image_url = get_vacancy_image(link)
        email, ai_desc = analyze_job_with_gemini(image_url, title)
        
        if email:
            cur.execute("UPDATE job_listings SET contact_email = %s, job_description = %s WHERE id = %s", (email, ai_desc, job_id))
            conn.commit()
            print(f"   -> FIXED! Email: {email}")
        else:
            print("   -> Still no email found.")
            
    cur.close()
    conn.close()
    print("\nRepair finished. You can now run scraper.py to auto-apply!")

if __name__ == "__main__":
    repair()
