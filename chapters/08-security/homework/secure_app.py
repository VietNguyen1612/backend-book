import sqlite3
import os

SECRET_API_KEY = "sk-1234567890abcdef" # BAD: Hardcoded secret

def get_user_data(username):
    # BAD: SQL Injection vulnerability
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()

def read_user_file(filename):
    # BAD: Path Traversal vulnerability
    filepath = "/var/app/data/" + filename
    with open(filepath, 'r') as f:
        return f.read()

# TODO: Refactor the above code to be secure.
# 1. Use environment variables for secrets.
# 2. Use parameterized queries for SQL.
# 3. Sanitize or validate file paths.
