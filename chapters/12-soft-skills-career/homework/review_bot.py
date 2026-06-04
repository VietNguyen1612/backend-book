def scan_diff_for_aggressive_language(diff_text: str) -> list[str]:
    flags = ["stupid", "idiot", "wtf", "hate", "dumb"]
    findings = []
    
    # TODO: Analyze the diff_text and return a list of warnings if aggressive words are found.
    # Also, suggest a more constructive phrasing.
    
    return findings

if __name__ == "__main__":
    sample_diff = """
    + # This is a stupid hack because the API is broken
    + def workaround():
    +     pass
    """
    print(scan_diff_for_aggressive_language(sample_diff))
