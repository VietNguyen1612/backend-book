class Span:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        pass
    def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO: Calculate and log duration
        pass
