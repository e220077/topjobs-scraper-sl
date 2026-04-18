import psycopg2
import sys

# Database Configuration
DB_CONFIG = {
    "dbname": "job",
    "user": "batman",
    "password": "dinal123",
    "host": "localhost",
    "port": "5432"
}

def init_db():
    """
    Creates the 'job_listings' table in the PostgreSQL database.
    """
    commands = (
        """
        CREATE TABLE IF NOT EXISTS job_listings (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255),
            job_link TEXT UNIQUE NOT NULL,
            image_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    conn = None
    try:
        # connect to the PostgreSQL server
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        # create table one by one
        for command in commands:
            cur.execute(command)
        # close communication with the PostgreSQL database server
        cur.close()
        # commit the changes
        conn.commit()
        print("Database initialized successfully: Table 'job_listings' is ready.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error initializing database: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    init_db()
