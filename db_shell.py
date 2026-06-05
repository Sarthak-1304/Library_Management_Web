import sqlite3

def run_shell():
    conn = sqlite3.connect("library.db")
    cur = conn.cursor()
    print("=== Interactive SQLite Database Shell ===")
    print("Type '.tables' to see tables, '.schema <table_name>' to view columns.")
    print("Or write any SELECT SQL query. Type 'exit' to quit.\n")
    
    while True:
        try:
            query = input("sqlite> ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", ".exit", ".quit"]:
                break
                
            if query.lower() == ".tables":
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [r[0] for r in cur.fetchall() if r[0] != "sqlite_sequence"]
                print("Tables: " + ", ".join(tables))
                continue
                
            if query.lower().startswith(".schema"):
                parts = query.split()
                if len(parts) > 1:
                    t_name = parts[1]
                    cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (t_name,))
                    res = cur.fetchone()
                    if res:
                        print(res[0])
                    else:
                        print(f"Table '{t_name}' not found.")
                else:
                    print("Usage: .schema <table_name>")
                continue

            # Run standard query
            cur.execute(query)
            
            if query.lower().startswith("select"):
                rows = cur.fetchall()
                if not rows:
                    print("No results returned.")
                    continue
                
                # Print column headers
                headers = [desc[0] for desc in cur.description]
                header_line = " | ".join(headers)
                print(header_line)
                print("-" * len(header_line))
                
                # Print rows
                for row in rows:
                    print(" | ".join(str(val) for val in row))
            else:
                conn.commit()
                print("Statement executed and committed.")
                
        except Exception as e:
            print(f"Error: {e}")
            
    conn.close()

if __name__ == "__main__":
    run_shell()
