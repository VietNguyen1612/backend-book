class Author:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class Book:
    def __init__(self, id, title, author_id):
        self.id = id
        self.title = title
        self.author_id = author_id

# Mock database tables
AUTHORS = [Author(1, "J.K. Rowling"), Author(2, "George R.R. Martin")]
BOOKS = [Book(101, "Harry Potter", 1), Book(102, "Game of Thrones", 2), Book(103, "Clash of Kings", 2)]

def get_author_by_id(author_id):
    print(f"QUERY: SELECT * FROM author WHERE id = {author_id}")
    return next((a for a in AUTHORS if a.id == author_id), None)

def get_all_books():
    print("QUERY: SELECT * FROM book")
    return BOOKS

# BAD: N+1 Problem
def print_books_and_authors_bad():
    books = get_all_books()
    for book in books:
        author = get_author_by_id(book.author_id)
        print(f"{book.title} by {author.name}")

# TODO: Implement a better version that fetches all necessary authors in ONE query
# def print_books_and_authors_good():
#     pass
