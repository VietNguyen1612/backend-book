[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 2.1 Language Internals

Chapter 1 dealt in fundamentals that hold for any language — data structures, operating systems, databases, networks. With this chapter we narrow the lens to Python itself, and we start at the bottom: how the interpreter actually represents objects, manages memory, and schedules threads. These are not academic concerns. They are the difference between a Django worker that holds steady at 200 MB and one that climbs until the OOM killer takes it down; between an endpoint that gets faster when you add threads and one that mysteriously gets slower; between an ORM whose field validation you can extend confidently and one you treat as magic. When production misbehaves in ways the application code cannot explain, the explanation almost always lives at this layer.

By the end of this section you should be able to answer questions like: why does adding `__slots__` cut a service's memory footprint nearly in half? How does Django implement `Model.objects` and field validation without any visible function calls? Why did deleting the last reference to an object not free its memory — and what eventually did? Why did a CPU-bound task get no faster with eight threads, and what should you reach for instead? And when a profiler points at a hot loop, what is CPython actually executing there?

The section follows the interpreter from the outside in. We begin with the **data model** — objects, descriptors, metaclasses, and the protocols that make Python's syntax programmable. We then look at **memory and garbage collection**: reference counting, the cycle collector, weak references, and the tools for finding leaks. That leads naturally to the **GIL**, the lock that makes reference counting safe and CPU-bound threading futile, along with its workarounds and its future. Finally we descend into **CPython internals** — bytecode, frame objects, and the small-object allocator — to see what the virtual machine does with the code you write.

## Data Model

We start with the single idea from which the rest of Python's behavior follows: everything the interpreter touches is an object governed by a small set of protocols. Attribute access, operator syntax, even class creation itself are all hooks you can intercept — and the frameworks you use every day, from Django's ORM to pytest, are built on exactly these hooks.

### Everything Is an Object

In Python, **everything** is an object -- integers, strings, functions, classes, modules, even `None`. Every object has three fundamental properties: an **identity** (its memory address, retrieved via `id()`), a **type** (retrieved via `type()`), and a **value**. This uniformity is what makes Python so dynamic and flexible: you can pass functions as arguments, store classes in dictionaries, and introspect anything at runtime.

```python
# Everything is an object -- proof
def greet(name):
    return f"Hello, {name}"

print(type(42))             # <class 'int'>
print(type("hello"))        # <class 'str'>
print(type(greet))          # <class 'function'>
print(type(type))           # <class 'type'>
print(type(None))           # <class 'NoneType'>

# Functions are objects -- they have attributes
print(greet.__name__)       # 'greet'
print(greet.__code__.co_varnames)  # ('name',)

# You can attach arbitrary attributes to functions
greet.call_count = 0

# Objects have identity
a = [1, 2, 3]
b = a
c = [1, 2, 3]
print(id(a) == id(b))  # True  -- same object
print(id(a) == id(c))  # False -- different objects with same value
print(a is b)           # True  -- 'is' compares identity
print(a == c)           # True  -- '==' compares value
```

### `__slots__`: Memory-Efficient Attribute Storage

By default, Python objects store their attributes in a per-instance `__dict__` dictionary. This is flexible but costs significant memory -- each dictionary carries overhead for hash tables, resize capacity, and pointer indirection. `__slots__` declares a fixed set of allowed attributes, replacing the dictionary with a compact, tuple-like storage layout.

```python
import sys

# WITHOUT __slots__ -- uses __dict__
class PointRegular:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# WITH __slots__ -- compact storage
class PointSlotted:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y

regular = PointRegular(1.0, 2.0)
slotted = PointSlotted(1.0, 2.0)

print(sys.getsizeof(regular))               # ~48 bytes (object)
print(sys.getsizeof(regular.__dict__))       # ~104 bytes (dict overhead!)
print(sys.getsizeof(slotted))               # ~48 bytes (no dict)

# regular has __dict__, slotted does not
print(hasattr(regular, '__dict__'))  # True
print(hasattr(slotted, '__dict__'))  # False

# __slots__ prevents adding arbitrary attributes
regular.z = 3       # Works fine
try:
    slotted.z = 3   # AttributeError!
except AttributeError as e:
    print(e)  # 'PointSlotted' object has no attribute 'z'

# GOTCHA: Subclass must also declare __slots__, or it gets __dict__ back
class PointSlotted3D(PointSlotted):
    __slots__ = ('z',)  # Only declare NEW attributes

    def __init__(self, x, y, z):
        super().__init__(x, y)
        self.z = z

# Practical impact: creating 1 million objects
import tracemalloc
tracemalloc.start()
points = [PointSlotted(i, i) for i in range(1_000_000)]
current, peak = tracemalloc.get_traced_memory()
print(f"Slotted: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()

tracemalloc.start()
points = [PointRegular(i, i) for i in range(1_000_000)]
current, peak = tracemalloc.get_traced_memory()
print(f"Regular: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
# Typical result: Slotted ~56 MB, Regular ~160+ MB (saves ~40-60%)
```

### Descriptors: The Machinery Behind Properties and Methods

Descriptors are objects that define any of `__get__`, `__set__`, or `__delete__`. They control what happens when an attribute is accessed on an instance. Descriptors are the foundation of `property`, `classmethod`, `staticmethod`, and ORM field definitions. Understanding descriptors means understanding how Python attribute access actually works.

There are two kinds:

- **Data descriptors**: define both `__get__` and `__set__` (or `__delete__`). They take priority over instance `__dict__`.
- **Non-data descriptors**: define only `__get__`. Instance `__dict__` takes priority over them.

```python
# -- A data descriptor: validated attribute --
class Positive:
    """Descriptor that enforces positive numeric values."""
    def __set_name__(self, owner, name):
        self.name = name
        self.private_name = f'_desc_{name}'

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # Accessed on the class itself
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f'{self.name} must be numeric')
        if value <= 0:
            raise ValueError(f'{self.name} must be positive')
        setattr(obj, self.private_name, value)

    def __delete__(self, obj):
        delattr(obj, self.private_name)

class Product:
    price = Positive()     # Data descriptor
    quantity = Positive()  # Data descriptor

    def __init__(self, name, price, quantity):
        self.name = name
        self.price = price        # Goes through Positive.__set__
        self.quantity = quantity   # Goes through Positive.__set__

p = Product("Widget", 9.99, 100)
print(p.price)   # 9.99 -- goes through Positive.__get__

try:
    p.price = -5  # ValueError: price must be positive
except ValueError as e:
    print(e)

# -- Attribute lookup order (simplified) --
# 1. Data descriptors on the class (e.g., property, our Positive)
# 2. Instance __dict__
# 3. Non-data descriptors on the class (e.g., regular methods)
```

```
  Attribute Lookup Order
  ======================

  obj.attr
    |
    v
  [1] Data descriptor on type(obj)?  --> type(obj).attr.__get__(obj, type(obj))
    |  (defines __get__ + __set__)
    | no
    v
  [2] 'attr' in obj.__dict__?        --> obj.__dict__['attr']
    |
    | no
    v
  [3] Non-data descriptor on type(obj)? --> type(obj).attr.__get__(obj, type(obj))
    |  (defines only __get__)
    | no
    v
  [4] Class attribute?                --> type(obj).attr
    |
    | no
    v
  [5] AttributeError
```

### Metaclasses: The Class of a Class

A metaclass is the "type" of a class. Just as an object is an instance of a class, a class is an instance of its metaclass. The default metaclass is `type`. Metaclasses let you customize class creation itself -- validating class definitions, auto-registering classes, transforming attributes, and more.

```python
# type is the metaclass of all classes by default
class Foo:
    pass

print(type(Foo))      # <class 'type'>
print(type(type))     # <class 'type'> -- type is its own metaclass!

# -- Creating a class dynamically with type() --
# type(name, bases, namespace) creates a new class
Dog = type('Dog', (), {
    'species': 'Canis familiaris',
    'speak': lambda self: 'Woof!'
})
print(Dog().speak())  # Woof!

# -- Custom metaclass example: auto-registry --
class PluginMeta(type):
    """Metaclass that auto-registers all subclasses into a registry."""
    registry = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # Don't register the base class itself
        if bases:
            PluginMeta.registry[name] = cls
        return cls

class Plugin(metaclass=PluginMeta):
    """Base class for all plugins."""
    pass

class AuthPlugin(Plugin):
    pass

class CachePlugin(Plugin):
    pass

print(PluginMeta.registry)
# {'AuthPlugin': <class 'AuthPlugin'>, 'CachePlugin': <class 'CachePlugin'>}

# -- Simpler alternative: __init_subclass__ (Python 3.6+) --
class Plugin:
    _registry = {}

    def __init_subclass__(cls, plugin_name=None, **kwargs):
        super().__init_subclass__(**kwargs)
        name = plugin_name or cls.__name__
        Plugin._registry[name] = cls

class AuthPlugin(Plugin, plugin_name="auth"):
    pass

class CachePlugin(Plugin):  # Uses class name by default
    pass

print(Plugin._registry)
# {'auth': <class 'AuthPlugin'>, 'CachePlugin': <class 'CachePlugin'>}
```

Use `__init_subclass__` when possible -- it is simpler and covers most use cases (registration, validation, attribute injection). Resort to full metaclasses only when you need to control `__new__` (class creation itself) or modify the class namespace during construction.

### `__new__` vs `__init__`

`__new__` is the constructor that **creates** the instance. `__init__` is the initializer that **configures** it after creation. For mutable types, you rarely override `__new__`. But for immutable types (like `str`, `int`, `tuple`), you must use `__new__` because by the time `__init__` runs, the object's value is already frozen.

```python
# -- Immutable type: must use __new__ --
class UpperStr(str):
    """A string subclass that is always uppercase."""
    def __new__(cls, value):
        # str is immutable -- must set value in __new__
        instance = super().__new__(cls, value.upper())
        return instance

s = UpperStr("hello")
print(s)         # HELLO
print(type(s))   # <class 'UpperStr'>

# -- Singleton pattern using __new__ --
class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, value=None):
        # __init__ runs every time Singleton() is called!
        if value is not None:
            self.value = value

a = Singleton("first")
b = Singleton("second")
print(a is b)       # True  -- same instance
print(a.value)      # "second" -- __init__ ran again!
```

### MRO (Method Resolution Order)

Python uses the **C3 linearization** algorithm to determine the order in which base classes are searched when looking up a method. This is critical in diamond inheritance scenarios. `super()` follows the MRO, not just the "parent" class.

```python
class A:
    def who(self):
        print("A", end=" -> ")

class B(A):
    def who(self):
        print("B", end=" -> ")
        super().who()

class C(A):
    def who(self):
        print("C", end=" -> ")
        super().who()

class D(B, C):
    def who(self):
        print("D", end=" -> ")
        super().who()

print(D.mro())
# [D, B, C, A, object]

D().who()
# D -> B -> C -> A ->

#   Diamond Inheritance & MRO
#
#        A
#       / \
#      B   C
#       \ /
#        D
#
#   MRO: D -> B -> C -> A -> object
#   super() in B does NOT go to A -- it goes to C (next in MRO)
```

### Dunder (Magic) Methods

Dunder methods let your objects integrate with Python's syntax and built-in functions. Here are the most important ones demonstrated together:

```python
class Money:
    def __init__(self, amount, currency="USD"):
        self.amount = amount
        self.currency = currency

    def __repr__(self):
        """Unambiguous representation for developers / debugging."""
        return f"Money({self.amount!r}, {self.currency!r})"

    def __str__(self):
        """Readable representation for end users."""
        symbols = {"USD": "$", "EUR": "E", "GBP": "L"}
        sym = symbols.get(self.currency, self.currency)
        return f"{sym}{self.amount:.2f}"

    def __eq__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self):
        """Must be consistent with __eq__."""
        return hash((self.amount, self.currency))

    def __bool__(self):
        """Money is 'truthy' if amount is nonzero."""
        return self.amount != 0

    def __add__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __lt__(self, other):
        if not isinstance(other, Money) or self.currency != other.currency:
            return NotImplemented
        return self.amount < other.amount

    def __len__(self):
        """Number of whole currency units."""
        return int(abs(self.amount))

    def __call__(self, exchange_rate, target_currency):
        """Convert to another currency."""
        return Money(self.amount * exchange_rate, target_currency)

# Usage
price = Money(19.99)
tax = Money(1.60)
total = price + tax

print(repr(total))    # Money(21.59, 'USD')
print(str(total))     # $21.59
print(bool(Money(0))) # False
print(len(price))     # 19

# callable -- convert currency
eur_price = price(0.92, "EUR")
print(eur_price)      # E18.39

# hashable -- can use in sets and as dict keys
prices = {Money(9.99, "USD"), Money(9.99, "EUR"), Money(9.99, "USD")}
print(len(prices))    # 2 (duplicates removed)
```

### `__init_subclass__`: Simpler Than Metaclasses

`__init_subclass__` is called on the parent class whenever a subclass is created. It provides a clean hook for class-level validation, registration, and attribute injection without the complexity of metaclasses.

```python
class Serializable:
    """Base class that requires subclasses to declare a 'version' attribute."""
    _versions = {}

    def __init_subclass__(cls, version=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if version is None:
            raise TypeError(f"{cls.__name__} must declare a version")
        cls.version = version
        Serializable._versions[cls.__name__] = version

class UserData(Serializable, version=1):
    pass

class ConfigData(Serializable, version=3):
    pass

print(Serializable._versions)
# {'UserData': 1, 'ConfigData': 3}

# This would raise TypeError:
# class BadData(Serializable):
#     pass
```

> **Key Takeaway:** Python's data model is built on a small set of powerful protocols -- descriptors, dunder methods, metaclasses, and MRO. Mastering these lets you write code that integrates seamlessly with the language itself. Prefer `__init_subclass__` over metaclasses, use `__slots__` when you have many instances, and always implement `__repr__` on your classes.

---

## Memory & Garbage Collection

Every object we just described — every instance, every descriptor, every class — occupies memory, and something must decide when that memory can be reclaimed. Python makes that decision automatically, but the mechanism is observable: it shapes when destructors run, why certain caches leak, and where a long-running worker's memory actually goes. This section examines the two-tier scheme CPython uses and the tools for inspecting it.

### Reference Counting

Python's primary garbage collection mechanism is **reference counting**. Every object maintains a count of how many references point to it. When the count drops to zero, the object is deallocated immediately. This gives Python deterministic cleanup behavior -- resources are freed as soon as the last reference disappears.

```python
import sys

# sys.getrefcount() itself adds a temporary reference, so counts are +1
a = []
print(sys.getrefcount(a))  # 2 (a + getrefcount's parameter)

b = a
print(sys.getrefcount(a))  # 3 (a + b + getrefcount's parameter)

c = [a, a, a]
print(sys.getrefcount(a))  # 6 (a + b + 3 in list + getrefcount's parameter)

del b
print(sys.getrefcount(a))  # 5

# When refcount hits 0, __del__ is called (if defined)
class Noisy:
    def __init__(self, name):
        self.name = name
        print(f"  Created {self.name}")

    def __del__(self):
        print(f"  Destroyed {self.name}")

print("--- Creating ---")
obj = Noisy("test")         # Created test
print("--- Replacing ---")
obj = Noisy("replacement")  # Destroyed test  (immediate! refcount hit 0)
                             # Created replacement
print("--- Done ---")
```

```
  Reference Counting in Action
  ============================

  a = MyObject()
     refcount: 1       a ----> [MyObject]

  b = a
     refcount: 2       a ----> [MyObject] <---- b

  del a
     refcount: 1       [MyObject] <---- b

  del b
     refcount: 0       [MyObject]  --> DEALLOCATED
```

### Generational Garbage Collector

Reference counting cannot handle **circular references** -- when objects reference each other, their refcounts never reach zero even if they are unreachable from the program. Python's generational GC detects and collects these cycles.

```python
import gc

# -- Circular reference that refcounting can't handle --
class Node:
    def __init__(self, name):
        self.name = name
        self.partner = None

    def __del__(self):
        pass  # Note: __del__ with cycles was problematic before Python 3.4

# Create a cycle
a = Node("A")
b = Node("B")
a.partner = b
b.partner = a  # Circular reference!

# Even after deleting our references, the objects keep each other alive
del a
del b
# Objects still exist in memory! refcount is 1 for each (partner reference)

# The generational GC must find and collect them
collected = gc.collect()
print(f"Collected {collected} objects")

# -- Understanding generations --
print(gc.get_threshold())  # (700, 10, 10) - default thresholds
# Generation 0: collected every 700 allocations (minus deallocations)
# Generation 1: collected every 10 gen0 collections
# Generation 2: collected every 10 gen1 collections

# Inspect what's in each generation
print(f"Gen 0: {len(gc.get_objects(0))} objects")
print(f"Gen 1: {len(gc.get_objects(1))} objects")
print(f"Gen 2: {len(gc.get_objects(2))} objects")

# -- Disable GC for performance-critical sections --
gc.disable()
# ... allocate many objects that you know have no cycles ...
gc.enable()
gc.collect()  # Force a full collection
```

Running this prints something like (object counts depend on what your process has already imported):

```text
Collected 2 objects
(700, 10, 10)
Gen 0: 312 objects
Gen 1: 1894 objects
Gen 2: 28571 objects
```

**What's happening:** `gc.collect()` returns the number of unreachable objects it freed -- here `2`, the two `Node` instances that formed the cycle. This is the proof that refcounting alone left them alive: their refcounts never hit zero because each held a reference to the other. The threshold tuple `(700, 10, 10)` is the tuning knob -- gen-0 runs after 700 net allocations, and each higher generation runs only after 10 collections of the one below it, so the oldest (mostly long-lived) objects are scanned least often. The lopsided per-generation counts are normal: a steady-state web worker accumulates thousands of long-lived objects (modules, route tables, connection pools) in gen 2, which is exactly why scanning gen 2 rarely keeps GC pauses small.

> **Common pitfall:** Defining `__del__` on objects that participate in reference cycles used to make them *uncollectable* (Python parked them in `gc.garbage` instead of freeing them). Since Python 3.4 the collector can finalize most such cycles, but the ordering of `__del__` calls is still undefined -- never rely on `__del__` for critical cleanup; use `contextlib`/`with` or `weakref.finalize` instead.

```
  Generational GC Layout
  ======================

  Gen 0 (youngest)      Gen 1 (middle)       Gen 2 (oldest)
  +-----------------+   +-----------------+   +-----------------+
  | New objects      |   | Survived 1      |   | Survived 2+     |
  | Collected most   |-->| collection      |-->| collections     |
  | frequently       |   | Less frequent   |   | Least frequent  |
  | Threshold: 700   |   | Threshold: 10   |   | Threshold: 10   |
  +-----------------+   +-----------------+   +-----------------+

  Objects that survive a collection are promoted to the next generation.
  Long-lived objects are checked less often --> reduces GC overhead.
```

### Weak References

A `weakref` is a reference to an object that does **not** increase its reference count. The object can be garbage-collected even if weak references to it exist. Weak references are invaluable for caches, observer patterns, and breaking circular references.

```python
import weakref

class ExpensiveResource:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"ExpensiveResource({self.name!r})"

# Regular reference keeps object alive
obj = ExpensiveResource("data")
weak = weakref.ref(obj)

print(weak())      # ExpensiveResource('data') -- object is alive
print(weak() is obj)  # True

del obj
print(weak())      # None -- object was collected!

# -- WeakValueDictionary for caches --
class ImageCache:
    """Cache that doesn't prevent garbage collection of images."""
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get_image(self, path):
        img = self._cache.get(path)
        if img is not None:
            print(f"  Cache hit: {path}")
            return img
        print(f"  Cache miss: {path}")
        img = self._load_image(path)
        self._cache[path] = img
        return img

    def _load_image(self, path):
        return ExpensiveResource(path)

cache = ImageCache()
img1 = cache.get_image("photo.jpg")  # Cache miss
img2 = cache.get_image("photo.jpg")  # Cache hit

del img1, img2
# Image can be garbage collected now -- WeakValueDictionary won't prevent it

# -- Weak references with callbacks --
def on_finalize(ref):
    print(f"Object referenced by {ref} has been garbage collected!")

obj = ExpensiveResource("temp")
weak = weakref.ref(obj, on_finalize)
del obj  # Triggers callback: "Object referenced by ... has been garbage collected!"

# -- weakref.finalize: guaranteed cleanup --
obj = ExpensiveResource("db_connection")
weakref.finalize(obj, print, "Cleanup: closing connection")
del obj  # Prints: "Cleanup: closing connection"
```

Run end-to-end, the executable parts (cache demo, callback, finalizer) print:

```text
  Cache miss: photo.jpg
  Cache hit: photo.jpg
Object referenced by <weakref at 0x7f...; dead> has been garbage collected!
Cleanup: closing connection
```

**How to read this output:** The first `get_image` is a miss (object built and stored), the second is a hit served straight from the `WeakValueDictionary` -- but the moment the last *strong* reference (`img1`/`img2`) is dropped, the entry vanishes on its own, so the cache can never be the thing that pins a freed image in memory. That is the whole point of a weak cache: it speeds up the hot path without becoming a memory leak. The `on_finalize` callback fires the instant the referent dies (the weakref now reports `dead`), and `weakref.finalize` gives you the same guarantee in a form that *also* runs at interpreter shutdown -- which is why it is the right tool for "close this connection/file no matter how the object goes away," far safer than `__del__`.

> **Common pitfall:** `WeakValueDictionary` only works for objects that *can* be weakly referenced. Built-in types like `int`, `str`, `tuple`, and `list` do **not** support weak references, so caching those values directly raises `TypeError: cannot create weak reference`. Wrap them in a small class (or cache a holder object) if you need weak semantics.

### Memory Profiling

Understanding where your program's memory goes is essential for optimizing resource usage. Python provides several tools for memory analysis.

```python
# -- tracemalloc: built-in memory tracking --
import tracemalloc

tracemalloc.start()

# Allocate some memory
data = [dict(index=i, value=i**2) for i in range(10000)]
more_data = [str(i) * 100 for i in range(10000)]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 5 memory allocations:")
for stat in top_stats[:5]:
    print(f"  {stat}")

current, peak = tracemalloc.get_traced_memory()
print(f"\nCurrent: {current / 1024:.1f} KB")
print(f"Peak:    {peak / 1024:.1f} KB")
tracemalloc.stop()

# -- Comparing two snapshots to find leaks --
tracemalloc.start()
snapshot1 = tracemalloc.take_snapshot()

# ... do some work ...
leaky_list = []
for i in range(10000):
    leaky_list.append(" " * 1000)

snapshot2 = tracemalloc.take_snapshot()
top_stats = snapshot2.compare_to(snapshot1, 'lineno')

print("\nMemory changes:")
for stat in top_stats[:5]:
    print(f"  {stat}")

tracemalloc.stop()

# -- sys.getsizeof: shallow size only --
import sys

my_list = [1, 2, 3, 4, 5]
print(f"List object itself: {sys.getsizeof(my_list)} bytes")
# Does NOT include the size of the integers inside the list!

# For deep (recursive) size:
def deep_getsizeof(obj, seen=None):
    """Recursively calculate the total memory of an object and its contents."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(deep_getsizeof(k, seen) + deep_getsizeof(v, seen)
                    for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_getsizeof(item, seen) for item in obj)
    return size

data = {"users": [{"name": "Alice", "scores": [95, 87, 92]}]}
print(f"Shallow: {sys.getsizeof(data)} bytes")
print(f"Deep:    {deep_getsizeof(data)} bytes")
```

Running this prints something like (exact bytes vary by platform and Python version):

```text
Top 5 memory allocations:
  .../language_demo.py:630: size=1041 KiB, count=10000, average=107 B
  .../language_demo.py:629: size=625 KiB, count=10000, average=64 B
  .../language_demo.py:629: size=547 KiB, count=20000, average=28 B
  .../language_demo.py:636: size=448 B, count=2, average=224 B
  .../language_demo.py:632: size=416 B, count=1, average=416 B

Current: 2256.7 KB
Peak:    2257.1 KB

Memory changes:
  .../language_demo.py:651: size=9766 KiB (+9766 KiB), count=10000 (+10000), average=1000 B

Shallow: 232 bytes
Deep:    574 bytes
```

**How to read this output:**

- **`statistics('lineno')`** aggregates every live allocation *by the source line that made it*, sorted largest-first. The top line (`630`) is the `str(i) * 100` list — 10,000 strings of ~107 bytes each. Line `629` appears twice because building a list of dicts allocates both the dict objects *and* the list of references to them. This is how you answer "which line is eating my memory?" in production: the filename:lineno points you straight at the culprit.
- **`current` vs `peak`** — `current` is what is still alive at the snapshot; `peak` is the high-water mark since `start()`. A large gap between them signals a transient spike (e.g. loading a whole file to transform it) that you could stream instead.
- **`compare_to(snapshot1, 'lineno')`** is the leak-hunting workhorse: it diffs two snapshots and shows the *delta* per line. The `+9766 KiB` on line `651` makes the growth obvious — wrap a suspected-leaky request handler between two snapshots and anything with a steadily climbing delta is your leak.
- **`sys.getsizeof` is shallow**: it reports the size of the container object itself, *not* what it references. The dict reports `232` bytes (its own hash table) while `deep_getsizeof` walks the references and reports `574` — the real footprint. The `seen` set guards against infinite recursion on cyclic references, and ensures shared objects are only counted once.

> **Common pitfall:** `tracemalloc` only tracks allocations made *after* `start()`, and adds ~25–30% memory overhead itself — keep it off in normal production and enable it only when investigating. Reaching for `sys.getsizeof` to size a nested structure is the classic mistake: it silently undercounts, because it never follows references.

### Interning: String and Integer Caching

Python automatically caches (interns) small integers and certain strings to save memory and speed up comparisons. Understanding this avoids confusion when using `is` vs `==`.

```python
import sys

# -- Small integer interning: -5 to 256 --
a = 256
b = 256
print(a is b)  # True -- same object (interned)

a = 257
b = 257
print(a is b)  # False -- different objects (not interned)
# IMPORTANT: Always use == for value comparison, not 'is'

# -- String interning: identifiers are interned automatically --
a = "hello"
b = "hello"
print(a is b)  # True -- simple strings are often interned

a = "hello world!"
b = "hello world!"
print(a is b)  # False -- strings with spaces/punctuation may not be interned

# -- Explicit string interning with sys.intern() --
# Useful when comparing many repeated strings (e.g., parsing log files)
a = sys.intern("very_long_repeated_key_name")
b = sys.intern("very_long_repeated_key_name")
print(a is b)  # True -- guaranteed same object
# 'is' comparison is O(1) pointer compare vs O(n) string compare
```

> **Key Takeaway:** Python uses reference counting for immediate cleanup and generational GC for circular references. Use `tracemalloc` to find memory issues, `weakref` for caches that should not prevent garbage collection, and `__slots__` for classes with many instances. Always use `==` for value comparison, never `is` (which checks identity).

---

## GIL (Global Interpreter Lock)

The reference counting we just examined has a price: incrementing and decrementing counts from multiple threads at once would corrupt them without synchronization. CPython's answer is a single global lock rather than per-object locks — a design choice that keeps single-threaded code fast but constrains how Python programs can use multiple cores, with direct consequences for how you architect concurrent backend services.

The GIL is a mutex that protects access to Python objects, ensuring only one thread executes Python bytecode at a time. This simplifies CPython's memory management (reference counting is not thread-safe without it) but means that **CPU-bound** multithreaded programs cannot use multiple cores.

```python
import threading
import time

# -- The GIL in action: CPU-bound work does NOT parallelize --

def cpu_bound(n):
    """Count to n (pure Python CPU work)."""
    total = 0
    for i in range(n):
        total += i
    return total

N = 20_000_000

# Sequential
start = time.perf_counter()
cpu_bound(N)
cpu_bound(N)
sequential_time = time.perf_counter() - start
print(f"Sequential: {sequential_time:.2f}s")

# Threaded (NOT faster due to GIL!)
start = time.perf_counter()
t1 = threading.Thread(target=cpu_bound, args=(N,))
t2 = threading.Thread(target=cpu_bound, args=(N,))
t1.start(); t2.start()
t1.join(); t2.join()
threaded_time = time.perf_counter() - start
print(f"Threaded:   {threaded_time:.2f}s")
# Threaded is often SLOWER due to GIL contention overhead!

# -- I/O-bound work DOES benefit from threading --
import urllib.request

def fetch_url(url):
    """I/O-bound: GIL is released during network wait."""
    urllib.request.urlopen(url)

# During I/O wait, the GIL is released, letting other threads run.
```

On a typical multi-core machine (GIL build, pre-3.13 or default 3.13), this prints something like:

```text
Sequential: 1.18s
Threaded:   1.27s
```

**How to read this output:** Two cores, two threads, identical CPU work -- and the threaded version is *slower*, not 2x faster. The GIL lets only one thread execute Python bytecode at a time, so the two threads take turns instead of running in parallel; the extra time is pure overhead from acquiring/releasing the GIL and context-switching. This is the canonical interview answer to "why didn't `threading` speed up my number-crunching?" -- and the canonical production mistake of reaching for threads on a CPU-bound endpoint. For I/O-bound work the picture flips: `urlopen` releases the GIL while blocked on the socket, so other threads run during the wait and you get real concurrency.

```
  GIL and Thread Scheduling
  =========================

  CPU-Bound (GIL blocks parallelism):

  Thread 1: [===RUN===].............[===RUN===].....
  Thread 2: ............[===RUN===].............[===]
  GIL:      ^--T1 has--^^--T2 has--^^--T1 has--^
            Only ONE thread runs Python bytecode at a time.

  I/O-Bound (GIL released during I/O):

  Thread 1: [RUN][---I/O wait---][RUN]
  Thread 2:      [RUN][---I/O wait---][RUN]
  Thread 3:           [RUN][---I/O wait---][RUN]
  GIL:      ^T1^ ^T2^ ^T3^ (released during I/O, threads overlap)
```

### Workarounds for the GIL

```python
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import time

def cpu_work(n):
    return sum(i * i for i in range(n))

N = 10_000_000

# -- ProcessPoolExecutor: bypasses GIL with separate processes --
start = time.perf_counter()
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(cpu_work, N) for _ in range(4)]
    results = [f.result() for f in futures]
print(f"Multiprocessing: {time.perf_counter() - start:.2f}s")

# -- ThreadPoolExecutor: good for I/O-bound work --
import urllib.request

def fetch(url):
    return urllib.request.urlopen(url).read()[:100]

urls = ["https://example.com"] * 10
start = time.perf_counter()
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(fetch, urls))
print(f"Threaded I/O: {time.perf_counter() - start:.2f}s")

# -- NumPy releases the GIL for C-level operations --
import numpy as np

# This actually DOES benefit from multiple threads because
# NumPy's C code releases the GIL during computation.
a = np.random.rand(10_000_000)
result = np.sum(a ** 2)  # GIL released during numpy operations
```

The two timed sections print something like (exact numbers depend on core count, network latency, and process-startup cost):

```text
Multiprocessing: 0.71s
Threaded I/O: 0.34s
```

**How to read this output:** `ProcessPoolExecutor` runs each `cpu_work` call in a *separate OS process*, each with its own interpreter and its own GIL -- so four CPU-bound tasks genuinely run on four cores. The catch (visible if `N` were small) is process startup and the pickling of arguments/results across the process boundary, which is why processes win only when the work per task clearly outweighs that fixed cost. `ThreadPoolExecutor` shines on the I/O side: ten `urlopen` calls overlap their network waits under five worker threads, finishing in roughly the time of the two slowest requests rather than the sum of all ten. The practical rule this output encodes: **processes for CPU, threads for I/O.**

> **Common pitfall:** Code under a `ProcessPoolExecutor` must live behind an `if __name__ == "__main__":` guard (on Windows and macOS `spawn`), and every argument and return value must be picklable. Passing a lambda, an open file handle, or a database connection into a worker process raises a `PicklingError` or silently re-opens resources you did not expect.

### PEP 703: Free-Threaded Python (3.13+)

Starting with Python 3.13, an experimental free-threaded build is available that removes the GIL entirely. This is a major change with a gradual transition plan.

```python
# Check whether this interpreter is a free-threaded build (3.13+)
import sysconfig
print(bool(sysconfig.get_config_var("Py_GIL_DISABLED")))  # True on a free-threaded build
# At runtime you can also ask whether the GIL is currently active (3.13+):
# import sys; print(sys._is_gil_enabled())  # False when free-threaded

# In free-threaded Python, CPU-bound threads truly run in parallel.
# But: all your code and libraries must be thread-safe!
# This includes:
#   - No shared mutable state without locks
#   - C extensions must be updated for thread safety
#   - Reference counting uses atomic operations (slight overhead)

# Practical guidance for today:
# - Use threading for I/O-bound tasks (network, file, database)
# - Use multiprocessing for CPU-bound tasks (computation, ML)
# - Use asyncio for high-concurrency I/O (thousands of connections)
# - Keep an eye on free-threaded Python for future CPU-bound threading
```

> **Key Takeaway:** The GIL prevents CPU-bound parallelism in threads but does not affect I/O-bound work or multiprocessing. Use `ThreadPoolExecutor` for I/O-bound tasks, `ProcessPoolExecutor` for CPU-bound tasks, and `asyncio` for high-concurrency I/O. Free-threaded Python (PEP 703) is coming but requires a thread-safety mindset.

---

## CPython Internals

So far we have treated the interpreter's behavior — objects, garbage collection, the GIL — from the outside. We close the section by going one level deeper, into the machinery that executes your code: the bytecode the compiler produces, the frame objects that hold execution state, and the allocator that serves the millions of small allocations a Python process makes. This is the layer a profiler ultimately points at, and knowing it turns performance folklore into explanations.

### Bytecode Compilation and Execution

Python source code is compiled to **bytecode** -- a low-level, platform-independent representation that runs on CPython's stack-based virtual machine. Understanding bytecode helps you reason about performance and understand what Python actually does with your code.

```python
import dis

# -- Inspecting bytecode --
def add_squares(a, b):
    return a**2 + b**2

dis.dis(add_squares)
# Output (simplified):
#   LOAD_FAST     0 (a)
#   LOAD_CONST    1 (2)
#   BINARY_OP     8 (**)
#   LOAD_FAST     1 (b)
#   LOAD_CONST    1 (2)
#   BINARY_OP     8 (**)
#   BINARY_OP     0 (+)
#   RETURN_VALUE

# -- Comparing bytecode to understand performance --
def loop_append():
    result = []
    for i in range(1000):
        result.append(i * 2)
    return result

def list_comprehension():
    return [i * 2 for i in range(1000)]

print("--- loop_append ---")
dis.dis(loop_append)
print("\n--- list_comprehension ---")
dis.dis(list_comprehension)
# List comprehension has a dedicated BUILD_LIST opcode and runs in a
# tighter loop -- typically 20-30% faster than manual append.

# -- Accessing the code object --
code = add_squares.__code__
print(f"Name:       {code.co_name}")
print(f"Arg count:  {code.co_argcount}")
print(f"Local vars: {code.co_varnames}")
print(f"Constants:  {code.co_consts}")
print(f"Bytecode:   {code.co_code.hex()}")

# -- Why 'x in set' is faster than 'x in list' --
def search_list(x, data):
    return x in data

def search_set(x, data):
    return x in data

# Both produce the same CONTAINS_OP bytecode, but the runtime behavior
# differs: list.__contains__ is O(n), set.__contains__ is O(1).
```

The code-object introspection block prints (the hex bytecode varies by Python version):

```text
Name:       add_squares
Arg count:  2
Local vars: ('a', 'b')
Constants:  (None, 2)
Bytecode:   97007c00640213007c016402130013000100530000000000
```

**How to read this output:** A `__code__` object is the compiled, immutable result of your function -- the part the VM actually executes. `co_argcount` and `co_varnames` are how tools like `inspect.signature`, debuggers, and frameworks (pytest fixtures, FastAPI dependency injection) discover what a function expects without ever calling it. Notice `co_consts` contains `2` *and* `None`: the literal `2` is the exponent baked in as a constant, and `None` is the implicit return value Python adds to every function. `co_code` is the raw bytecode `dis` was decoding for you -- the same information, just human-readable. In production this matters because the compiler hoists literals into `co_consts` once instead of rebuilding them each call, which is part of why pulling a constant out of a hot loop is rarely worth it but recomputing an expression inside one can be.

### Frame Objects: The Execution Context

Every function call creates a **frame object** that holds the execution state: local variables, global references, the code object, and the instruction pointer. Frames form a stack that represents the call chain.

```python
import inspect
import sys

def outer():
    x = 10
    inner()

def inner():
    y = 20
    # Inspect the current frame
    frame = inspect.currentframe()
    print(f"Current function: {frame.f_code.co_name}")
    print(f"Local vars:       {frame.f_locals}")
    print(f"Line number:      {frame.f_lineno}")

    # Walk up the call stack
    caller = frame.f_back
    print(f"Caller function:  {caller.f_code.co_name}")
    print(f"Caller locals:    {caller.f_locals}")

    # Full stack trace
    for fi in inspect.stack():
        print(f"  {fi.function} at line {fi.lineno} in {fi.filename}")

    del frame  # Avoid reference cycles with frame objects

outer()

# -- sys._getframe() for quick access --
def get_caller_name():
    """Return the name of the function that called this function."""
    return sys._getframe(1).f_code.co_name

def my_function():
    print(f"I was called by: {get_caller_name()}")

my_function()  # "I was called by: my_function" -- wait, it's the test scope
```

Calling `outer()` walks the live call stack and prints something like (filenames and line numbers depend on where you run it):

```text
Current function: inner
Local vars:       {'y': 20}
Line number:      966
Caller function:  outer
Caller locals:    {'x': 10}
  inner at line 977 in demo.py
  outer at line 968 in demo.py
  <module> at line 981 in demo.py
```

**How to read this output:** Each call pushes a frame, and `f_back` chains them into the stack you see in every traceback. `inner` can read not just its own `f_locals` (`{'y': 20}`) but the *caller's* (`{'x': 10}`) -- this introspection is exactly how logging libraries auto-capture the calling module/line, how `traceback` formats exceptions, and how debuggers show you variables at every level. The bottom of the chain is `<module>`, the top-level frame. The `del frame` in the code is not ceremony: frame objects reference the locals that reference the frame, forming a cycle, so holding onto a frame (or storing it on `self`) is a classic way to leak large objects until the cyclic GC eventually sweeps them.

> **Common pitfall:** `sys._getframe()` and frame walking are CPython implementation details -- they are fast and ubiquitous in logging/debugging code, but they are not guaranteed on PyPy/other implementations and the overhead is real in hot paths. Reach for them for diagnostics, not for routine control flow.

### Small Object Allocator (pymalloc)

CPython uses a custom memory allocator optimized for small objects (up to 512 bytes). This avoids the overhead of calling the system's `malloc` for every small allocation (which Python programs do constantly).

```
  CPython Memory Architecture (pymalloc)
  =======================================

  +----------------------------------------------------------+
  |                      Python Runtime                       |
  |  Object-specific allocators (int, list, dict, etc.)      |
  +----------------------------------------------------------+
  |                    pymalloc (small objects)               |
  |                                                          |
  |  Arena (256 KB)                                          |
  |  +----------------------------------------------------+  |
  |  | Pool (4 KB)   Pool (4 KB)   Pool (4 KB)   ...     |  |
  |  | +-----------+ +-----------+ +-----------+          |  |
  |  | | Block 8B  | | Block 16B | | Block 32B |          |  |
  |  | | Block 8B  | | Block 16B | | Block 32B |          |  |
  |  | | Block 8B  | | Block 16B | | Block 32B |          |  |
  |  | | ...       | | ...       | | ...       |          |  |
  |  | +-----------+ +-----------+ +-----------+          |  |
  |  +----------------------------------------------------+  |
  +----------------------------------------------------------+
  |                    C malloc (large objects > 512B)        |
  +----------------------------------------------------------+
  |                    OS / Virtual Memory                    |
  +----------------------------------------------------------+

  Size classes: 8, 16, 24, 32, ... 512 bytes (64 classes, 8-byte step)
  Each Pool serves one size class.
  Arenas are released back to OS when all their pools are empty.
```

```python
# You can observe pymalloc behavior indirectly
import sys

# Small integers are pre-allocated (interned)
print(sys.getsizeof(0))     # 28 bytes on 64-bit Python
print(sys.getsizeof(1))     # 28 bytes
print(sys.getsizeof(2**30)) # 32 bytes (needs more storage)

# Small objects are allocated by pymalloc (fast)
# Large objects go to system malloc

# -- PYTHONMALLOC environment variable --
# PYTHONMALLOC=debug  --> enable debug hooks (detect buffer overflows)
# PYTHONMALLOC=malloc --> use system malloc for everything (for Valgrind)

# -- In practice: why list.append() is amortized O(1) --
# Lists over-allocate: when they grow, they allocate MORE space than needed.
# Growth pattern: 0, 4, 8, 16, 24, 32, 40, 52, 64, ...
# This means most appends don't trigger reallocation.
lst = []
prev_size = sys.getsizeof(lst)
for i in range(20):
    lst.append(i)
    new_size = sys.getsizeof(lst)
    if new_size != prev_size:
        print(f"  Length {len(lst):2d}: resized {prev_size} -> {new_size} bytes")
        prev_size = new_size
```

The `getsizeof` probes and the growth loop print something like (sizes are for 64-bit CPython):

```text
28
28
32
  Length  1: resized 56 -> 88 bytes
  Length  5: resized 88 -> 120 bytes
  Length  9: resized 120 -> 184 bytes
  Length 17: resized 184 -> 248 bytes
```

**How to read this output:** The integers `0` and `1` both report `28` bytes (a fixed object header plus one machine word of value), while `2**30` needs `32` -- CPython's `int` is arbitrary-precision, so larger magnitudes simply use more digit-words. The list output is the more important lesson: notice the resizes do **not** happen on every append. The list jumps capacity in chunks (1, then 5, then 9, then 17 ...), over-allocating headroom so that most appends just write into already-reserved space. That over-allocation is *why* `list.append` is amortized O(1) -- the occasional expensive reallocation is spread across many cheap appends. This is also why preallocating with `[None] * n` (or using `array`/NumPy for numeric data) beats repeated `append` when the final size is known: you skip the intermediate copies entirely.

> **Key Takeaway:** CPython compiles your code to bytecode, executes it on a stack-based VM, and uses a specialized memory allocator for small objects. Use `dis` to understand what Python is actually doing, and understand that list comprehensions, set lookups, and local variable access are fast because of how bytecode works.

## Summary

In this section we descended through CPython's layers, from the object model down to the virtual machine. The unifying theme is that Python's "magic" is a small set of inspectable protocols, and that knowing them converts mysterious production behavior into mechanisms you can reason about.

The **data model** showed that everything is an object with identity, type, and value, and that attribute access, operators, and class creation are all programmable: descriptors implement properties and ORM fields, the MRO governs `super()` in diamond hierarchies, and `__init_subclass__` covers most cases people reach for metaclasses to solve. The working rules: prefer `__init_subclass__` over metaclasses, use `__slots__` when a class will have many instances, and always implement `__repr__`.

**Memory management** combines reference counting, which frees objects deterministically the moment their count hits zero, with a generational garbage collector that exists solely to break reference cycles. Use `weakref` for caches that must not pin their contents, `tracemalloc` (temporarily) to attribute memory to source lines, and never rely on `__del__` for critical cleanup.

The **GIL** is the cost of making reference counting thread-safe: only one thread executes bytecode at a time, so the decision rule is threads for I/O-bound work, processes for CPU-bound work, and `asyncio` for high-concurrency I/O — with free-threaded Python (PEP 703) on the horizon.

Finally, **CPython internals** explained the folklore: list comprehensions win because of dedicated opcodes, `append` is amortized O(1) because lists over-allocate, and frames held too long leak memory.

Concurrency surfaced here only as a constraint; the next section takes it up directly, with the event-loop model that dominates modern Python I/O — 2.2 Async Programming.

*Last reviewed: 2026-06-08*

**Next:** [2.2 Async Programming](async-programming.md)
