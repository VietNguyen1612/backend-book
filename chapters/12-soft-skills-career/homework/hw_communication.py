"""Communication Homework: Code Review Bot.

Write a function that scans a code-review diff (or comment) for unconstructive
/ aggressive language and returns a list of warnings, ideally suggesting more
constructive phrasing for each flagged term.
"""


def scan_diff_for_aggressive_language(diff_text: str) -> list:
    flags = ["stupid", "idiot", "wtf", "hate", "dumb"]
    findings = []

    # TODO: Analyze the diff_text and return a list of warnings if aggressive
    # words are found. Also, suggest a more constructive phrasing.

    return findings


if __name__ == "__main__":
    sample_diff = """
    + # This is a stupid hack because the API is broken
    + def workaround():
    +     pass
    """
    print(scan_diff_for_aggressive_language(sample_diff))
