class EventLoop:
    def __init__(self):
        self.tasks = []

    def add_task(self, coro):
        pass

    def run_until_complete(self):
        # TODO: Iterate over tasks using `send()` or `next()`
        pass
