"""Django Homework: N+1 Query Optimizer.

Simulate solving the classic N+1 query problem by bulk-fetching foreign keys
in memory instead of issuing one query per row.

The "bad" version issues one author query per book (N+1). Implement a "good"
version that fetches all required authors in a single query, then joins them
in memory.
"""


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
BOOKS = [
    Book(101, "Harry Potter", 1),
    Book(102, "Game of Thrones", 2),
    Book(103, "Clash of Kings", 2),
]


def get_author_by_id(author_id):
    print(f"QUERY: SELECT * FROM author WHERE id = {author_id}")
    return next((a for a in AUTHORS if a.id == author_id), None)


def get_authors_by_ids(author_ids):
    print(f"QUERY: SELECT * FROM author WHERE id IN {tuple(author_ids)}")
    return [a for a in AUTHORS if a.id in author_ids]


def get_all_books():
    print("QUERY: SELECT * FROM book")
    return BOOKS


# BAD: N+1 Problem (one author query per book)
def print_books_and_authors_bad():
    books = get_all_books()
    for book in books:
        author = get_author_by_id(book.author_id)
        print(f"{book.title} by {author.name}")


def print_books_and_authors_good():
    # TODO: Fetch all books, collect their author_ids, fetch the authors in ONE
    # query (use get_authors_by_ids), build an {id: author} map, then join in
    # memory so only TWO queries run in total.
    pass


if __name__ == "__main__":
    print("--- BAD (N+1) ---")
    print_books_and_authors_bad()
    print("--- GOOD (bulk fetch) ---")
    print_books_and_authors_good()
