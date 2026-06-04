# BAD CODE: Tightly coupled
import sqlite3
import smtplib

def register_user(username, email, password):
    # Database logic
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users VALUES (?, ?, ?)', (username, email, password))
    conn.commit()
    
    # Email logic
    server = smtplib.SMTP('localhost')
    server.sendmail('admin@app.com', email, f"Welcome {username}")
    server.quit()

# TODO: Refactor the above into a Hexagonal Architecture
# 1. Create IUserRepository and IEmailNotifier abstract base classes
# 2. Create SQLiteUserRepository and SMTPEmailNotifier implementations
# 3. Create a RegisterUserUseCase that takes these dependencies
