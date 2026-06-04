class LoggingMeta(type):
    # TODO: Intercept class creation and wrap methods with a logger
    pass

class MyService(metaclass=LoggingMeta):
    def do_work(self):
        print("Working...")
