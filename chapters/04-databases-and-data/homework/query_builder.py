class QueryBuilder:
    def __init__(self, table):
        self.table = table
        self._select = ["*"]
        self._where = []
        self._params = []
        self._limit = None

    def select(self, *columns):
        # TODO: Implement select
        return self

    def where(self, condition, value):
        # TODO: Implement where
        return self

    def limit(self, limit):
        # TODO: Implement limit
        return self

    def get_sql(self):
        # TODO: Return tuple of (sql_string, parameters_list)
        pass

# Example usage:
# qb = QueryBuilder("users").select("id", "name").where("age > ?", 18).limit(10)
# sql, params = qb.get_sql()
