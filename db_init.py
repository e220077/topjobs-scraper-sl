import psycopg2
import sys
import os

# Supabase Database URL (Pooler for IPv4)
DB_URL = os.getenv('DATABASE_URL')

def init_db():
    """
    Creates the 'job_listings' table in the Supabase PostgreSQL database.
    """
    commands = (
        """
        CREATE TABLE IF NOT EXISTS job_listings (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255),
            job_link TEXT UNIQUE NOT NULL,
            image_url TEXT,
            job_description TEXT,
            contact_email VARCHAR(255),
            application_sent BOOLEAN DEFAULT FALSE,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    conn = None
    try:
        if not DB_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        # connect to the Supabase server
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # create table one by one
        for command in commands:
            cur.execute(command)
        # close communication with the PostgreSQL database server
        cur.close()
        # commit the changes
        conn.commit()
        print("Database initialized successfully: Table 'job_listings' is now live on Supabase.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error initializing database: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    init_db()
