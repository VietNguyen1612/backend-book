class Field:
    # TODO: Implement the descriptor protocol (__get__, __set__)
    pass

class StringField(Field):
    pass

class IntField(Field):
    pass

class ModelMeta(type):
    # TODO: Implement metaclass logic to gather fields
    pass

class Model(metaclass=ModelMeta):
    # TODO: Implement base model logic
    pass

# Test your implementation:
# class User(Model):
#     name = StringField()
#     age = IntField()
# 
# u = User(name="Alice", age=30)
