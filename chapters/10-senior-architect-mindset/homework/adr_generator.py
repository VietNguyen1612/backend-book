import datetime

def generate_adr(title: str, context: str, decision: str, consequences: str) -> str:
    # TODO: Return a formatted Markdown string containing the ADR
    pass

if __name__ == "__main__":
    adr = generate_adr(
        title="Use ScyllaDB for Chat Message Storage",
        context="We need to store billions of messages with high write throughput.",
        decision="We will use ScyllaDB due to its wide-column architecture and performance.",
        consequences="Developers need to learn CQL. Operations team needs to manage a new database."
    )
    print(adr)
