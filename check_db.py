import sqlite3

def check_db():
    conn = sqlite3.connect("library.db")
    cur = conn.cursor()
    
    # Get list of tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    
    print("=== TABLES IN DATABASE ===")
    for table in tables:
        t_name = table[0]
        if t_name == "sqlite_sequence":
            continue
        cur.execute(f"SELECT COUNT(*) FROM {t_name};")
        count = cur.fetchone()[0]
        print(f" - {t_name}: {count} row(s)")
    print("==========================\n")
    
    # Show sample books
    print("Sample books (First 3):")
    cur.execute("SELECT isbn, title, author, available FROM books LIMIT 3;")
    for row in cur.fetchall():
        print(f"  ISBN: {row[0]} | Title: {row[1]} | Author: {row[2]} | Avail: {row[3]}")
        
    conn.close()

if __name__ == "__main__":
    check_db()
