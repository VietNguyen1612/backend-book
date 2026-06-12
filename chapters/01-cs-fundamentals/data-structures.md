[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.1 Data Structures

> [!NOTE]
> **Beginner's Mental Model — Arrays vs Linked Lists:**
> Think of an array as a row of numbered lockers side-by-side: if you know the locker number, you can open it instantly (O(1) random access), but inserting a new locker in the middle requires shifting all subsequent lockers down. A linked list is like a scavenger hunt where each clue points to the location of the next clue: you have to follow the trail from the beginning to find anything (O(n) access), but adding a new step just requires updating one clue to point to the new location (O(1) insertion).

### Arrays & Linked Lists

To understand how computer programs store lists of information, it helps to imagine two different ways of organizing physical items. Suppose you are setting up a row of numbered lockers side-by-side. If you need to find something in locker number five, you can walk directly to it without opening any other doors. However, if you want to squeeze a new locker right in the middle, you have to physically shift every single locker after it down by one slot. This is the core idea behind an array: items sit next to each other in a continuous line, making them incredibly fast to look up but slow and tedious to reorganize. Now imagine a scavenger hunt where each location contains a clue directing you to the next spot. You cannot jump straight to the fifth clue without following the trail from the very beginning. But if you want to add a new step to the hunt, you only need to write a new clue and update the previous clue to point to it, leaving all other locations untouched. This represents a linked list, where items are scattered but connected sequentially by pointers.

#### Arrays (Contiguous Memory Layout)

An array stores elements in a contiguous block of memory. Because elements sit side-by-side, you can jump directly to any element by computing its address: `base_address + index * element_size`. This gives arrays **O(1) random access**, which is their defining advantage.

The trade-off comes with insertions and deletions. Inserting an element in the middle requires shifting all subsequent elements one position to the right, making it an **O(n) operation**. Deletion similarly requires shifting elements left to close the gap.

```
Memory layout of an array [10, 20, 30, 40, 50]:

Address:  0x100  0x108  0x110  0x118  0x120
         +------+------+------+------+------+
         |  10  |  20  |  30  |  40  |  50  |
         +------+------+------+------+------+
Index:      0      1      2      3      4

Inserting 25 at index 2 requires shifting:
         +------+------+------+------+------+------+
         |  10  |  20  |  25  |  30  |  40  |  50  |
         +------+------+------+------+------+------+
                        ^^^^   ---- shifted right -->
```

In Python, the built-in `list` type is a **dynamic array**. It over-allocates memory using an amortized doubling strategy: when the internal buffer is full, Python allocates a new buffer roughly 1.125x the current size (the exact growth factor varies by implementation), copies all elements over, and frees the old buffer. This means that while a single `append` might occasionally trigger an O(n) copy, the average cost of appending is **amortized O(1)**.

```python
import sys

# Observe how Python list over-allocates memory
sizes = []
lst = []
for i in range(50):
    lst.append(i)
    sizes.append(sys.getsizeof(lst))

# Print size changes — you'll see the size jumps in chunks, not one element at a time
for i in range(1, len(sizes)):
    if sizes[i] != sizes[i - 1]:
        print(f"At length {i}: size changed from {sizes[i-1]} to {sizes[i]} bytes")
```

Running this prints something like (exact byte counts vary by Python version and 32- vs 64-bit build):

```text
At length 4: size changed from 88 to 120 bytes
At length 8: size changed from 120 to 184 bytes
At length 16: size changed from 184 to 248 bytes
At length 24: size changed from 248 to 312 bytes
At length 32: size changed from 312 to 376 bytes
At length 40: size changed from 376 to 472 bytes
```

**How to read this output:** The size jumps happen in chunks (here at lengths 4, 8, 16, 24, 32, 40), not on every single `append`. Each jump is the moment Python's internal buffer filled up and was reallocated to a larger one — the backing buffer's capacity grows geometrically (4, 8, 16, 24, 32, 40, 52, ... on this 64-bit build) as the amortized over-allocation in action. Between jumps, `append` is touching pre-reserved slots and costs O(1). This is why `list.append` in a hot loop is cheap: you pay the occasional O(n) copy, but it is spread thin across many appends. In production, if you already know the final size, building via a list comprehension or pre-sizing avoids these intermediate reallocations entirely.

**Cache locality** is another critical advantage of arrays. Because elements are stored contiguously, accessing sequential elements loads them into the CPU cache together (a single cache line is typically 64 bytes). This makes iterating over arrays significantly faster in practice than iterating over linked lists, even when the theoretical Big-O is the same.

#### Linked Lists (Node-Based Memory Layout)

A linked list stores each element in a separate **node** that contains the data and a pointer (reference) to the next node. Nodes can be scattered anywhere in memory.

```
Singly Linked List: 10 -> 20 -> 30 -> 40 -> None

   +------+------+     +------+------+     +------+------+     +------+------+
   |  10  | next-+---->|  20  | next-+---->|  30  | next-+---->|  40  | None |
   +------+------+     +------+------+     +------+------+     +------+------+
   Node at 0x200        Node at 0x500        Node at 0x300        Node at 0x700
   (scattered in memory — no contiguity guarantee)

Doubly Linked List:

   None <--+------+------+------+     +------+------+------+     +------+------+------+--> None
           | prev |  10  | next-+---->| prev |  20  | next-+---->| prev |  30  | next |
           +------+------+------+     +------+------+------+     +------+------+------+
                                 <----+-                    <----+-
```

If you already have a reference to a node, inserting or deleting adjacent to it is **O(1)** — you just rewire the pointers. However, finding a node by index requires traversing from the head, which is **O(n)**.

Python's `collections.deque` is implemented as a **doubly-linked list of fixed-size blocks** (not individual nodes). This gives it efficient O(1) `append` and `appendleft`, as well as O(1) `pop` and `popleft`, making it ideal for queue and double-ended queue use cases.

```python
from collections import deque

# deque is optimized for both ends
dq = deque()
dq.append(1)          # Add to right: O(1)
dq.appendleft(0)      # Add to left:  O(1)
dq.pop()              # Remove from right: O(1)
dq.popleft()          # Remove from left:  O(1)

# Use as a fixed-size sliding window
window = deque(maxlen=5)
for i in range(10):
    window.append(i)
print(window)  # deque([5, 6, 7, 8, 9], maxlen=5)

# Using deque as a queue (FIFO)
task_queue = deque()
task_queue.append("task_1")   # enqueue
task_queue.append("task_2")
next_task = task_queue.popleft()  # dequeue: "task_1"
```

#### Circular Buffers (Ring Buffers)

A circular buffer is a fixed-size array that wraps around. It maintains two pointers — `head` (read position) and `tail` (write position). When either pointer reaches the end of the array, it wraps back to the beginning.

```
Ring Buffer (capacity=6, contains [A, B, C]):

     0     1     2     3     4     5
   +-----+-----+-----+-----+-----+-----+
   |     |     |  A  |  B  |  C  |     |
   +-----+-----+-----+-----+-----+-----+
                 ^head             ^tail

After writing D, E and reading A:

     0     1     2     3     4     5
   +-----+-----+-----+-----+-----+-----+
   |     |     |     |  B  |  C  |  D  |
   +-----+-----+-----+-----+-----+-----+
                       ^head             ^tail (wraps to 0 next)
```

```python
class RingBuffer:
    """A simple fixed-size circular buffer."""

    def __init__(self, capacity: int):
        self.buffer = [None] * capacity
        self.capacity = capacity
        self.head = 0  # read position
        self.tail = 0  # write position
        self.size = 0

    def write(self, item):
        if self.size == self.capacity:
            raise OverflowError("Buffer is full")
        self.buffer[self.tail] = item
        self.tail = (self.tail + 1) % self.capacity
        self.size += 1

    def read(self):
        if self.size == 0:
            raise IndexError("Buffer is empty")
        item = self.buffer[self.head]
        self.head = (self.head + 1) % self.capacity
        self.size -= 1
        return item

# Usage: producer-consumer pattern, log buffers, audio streaming
rb = RingBuffer(4)
rb.write("event_1")
rb.write("event_2")
rb.write("event_3")
print(rb.read())  # "event_1"
rb.write("event_4")
rb.write("event_5")  # Reuses the slot freed by the read
```

**When to use each:**

| Structure | Use When | Real-World Example |
|---|---|---|
| Array / `list` | Need indexed access, iteration, cache performance | Django QuerySet results, JSON arrays |
| Linked List / `deque` | Need fast insert/remove at both ends, FIFO queue | Task queues, BFS traversal, undo history |
| Circular Buffer | Fixed-size buffer, streaming data, producer-consumer | Log rotation, audio buffers, rate limiter sliding windows |

> **Key Takeaway:** The choice between arrays and linked lists is fundamentally about memory layout. Arrays win when you need random access and cache-friendly iteration. Linked lists (and deque) win when you need fast insertions/removals at both ends. In Python, prefer `list` for most cases and `collections.deque` when you need a queue. True linked lists are rarely hand-implemented in Python because the overhead per-node is high and cache locality is poor.

---

> [!NOTE]
> **Beginner's Mental Model — Hash Tables:**
> Imagine a coat check room. When you hand over your jacket, the attendant uses a quick rule (a hash function) to decide which hook to hang it on based on your ticket number. When you return, they don't search through every jacket one-by-one; they apply the same rule to your ticket and go straight to the correct hook.

### Hash Tables

Imagine you are running a busy coat check room at a theater. When guests hand you their jackets, you could hang them up in a random order, but finding them later would require searching through the entire rack one by one. Instead, you use a simple rule: you look at the first letter of the guest's last name and hang their coat on a hook corresponding to that letter. When a guest returns with their ticket, you apply the same rule to instantly locate their coat. A hash table works in the exact same way. It uses a mathematical rule called a hash function to take a key (like a guest's name) and calculate a specific index (the hook) where the corresponding value (the coat) should be stored. This allows you to find, add, or remove data almost instantly, bypassing the need to search through every entry in the system.

#### How Hash Tables Work

A hash table maps keys to values using a **hash function** that converts a key into an array index. A good hash function must be:

- **Deterministic**: same input always produces the same output.
- **Uniform distribution**: spreads keys evenly across buckets to minimize collisions.
- **Fast to compute**: hash computation happens on every operation.

When two keys hash to the same bucket (a **collision**), there are two main strategies:

```
Separate Chaining (linked list per bucket):

   Bucket 0:  [("apple", 5)] -> [("grape", 8)] -> None
   Bucket 1:  [("banana", 3)] -> None
   Bucket 2:  None
   Bucket 3:  [("cherry", 7)] -> [("date", 2)] -> None
   Bucket 4:  None

Open Addressing (linear probing — find next empty slot):

   Index:  0        1         2        3         4        5       6
         +--------+---------+--------+---------+--------+-------+-------+
         | apple  | banana  | grape  | cherry  |  date  | empty | empty |
         +--------+---------+--------+---------+--------+-------+-------+
                              ^-- "grape" hashed to 0, found occupied,
                                  probed forward to first empty slot
```

**Separate chaining** uses a linked list (or another structure) at each bucket. It handles high load gracefully but has worse cache performance due to pointer chasing. **Open addressing** stores everything in the array itself. When a collision occurs, it probes for the next open slot (linear probing, quadratic probing, or double hashing). It has better cache performance but degrades badly as the table fills up.

#### Load Factor and Rehashing

The **load factor** is `n/k` where `n` is the number of stored entries and `k` is the number of buckets. When the load factor exceeds a threshold (typically ~0.75 for chaining, ~0.5-0.7 for open addressing), the table **rehashes**: allocates a larger array (usually 2x) and reinserts all entries. This is an O(n) operation, but because it happens infrequently, insertions are **amortized O(1)**.

```python
# Simplified hash table with separate chaining
class SimpleHashTable:
    def __init__(self, initial_capacity=8):
        self.capacity = initial_capacity
        self.size = 0
        self.buckets = [[] for _ in range(self.capacity)]
        self.load_factor_threshold = 0.75

    def _hash(self, key):
        return hash(key) % self.capacity

    def put(self, key, value):
        if self.size / self.capacity >= self.load_factor_threshold:
            self._rehash()
        index = self._hash(key)
        bucket = self.buckets[index]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)  # Update existing
                return
        bucket.append((key, value))  # Insert new
        self.size += 1

    def get(self, key):
        index = self._hash(key)
        for k, v in self.buckets[index]:
            if k == key:
                return v
        raise KeyError(key)

    def _rehash(self):
        old_buckets = self.buckets
        self.capacity *= 2
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
        for bucket in old_buckets:
            for key, value in bucket:
                self.put(key, value)
```

#### Python dict Internals

Since Python 3.6, `dict` preserves insertion order. Internally, Python uses **open addressing with perturbation** (a form of randomized probing). The implementation uses two arrays:

1. A **sparse hash table** (indices array) that stores indices into a dense array.
2. A **dense entries array** that stores `(hash, key, value)` tuples in insertion order.

This **compact dict** design saves ~25% memory compared to the old implementation and guarantees insertion order as a language feature (formalized in Python 3.7).

Python also uses **key-sharing dictionaries** for instance `__dict__` attributes: when multiple instances of the same class exist, they share the keys array and each instance only stores its own values array. This saves significant memory for classes with many instances.

```python
from collections import OrderedDict, defaultdict, Counter

# defaultdict: auto-creates missing keys with a factory function
word_counts = defaultdict(int)
for word in "the cat sat on the mat the cat".split():
    word_counts[word] += 1
print(dict(word_counts))  # {'the': 3, 'cat': 2, 'sat': 1, 'on': 1, 'mat': 1}

# defaultdict with list — group items
from collections import defaultdict
users_by_role = defaultdict(list)
users = [("admin", "alice"), ("user", "bob"), ("admin", "carol"), ("user", "dave")]
for role, name in users:
    users_by_role[role].append(name)
# {'admin': ['alice', 'carol'], 'user': ['bob', 'dave']}

# Counter: specialized dict for counting
inventory = Counter(["apple", "banana", "apple", "cherry", "banana", "apple"])
print(inventory.most_common(2))  # [('apple', 3), ('banana', 2)]
# Counter supports arithmetic
new_shipment = Counter(["banana", "cherry", "cherry"])
inventory += new_shipment
# Counter({'apple': 3, 'banana': 3, 'cherry': 3})

# OrderedDict: useful when you need move_to_end or equality that considers order
od = OrderedDict()
od["first"] = 1
od["second"] = 2
od.move_to_end("first")  # Move to the end
# Now iteration order: "second", "first"
```

#### Consistent Hashing

In distributed systems, when you have N cache servers and use `hash(key) % N` to assign keys, adding or removing a server causes almost all keys to be remapped. **Consistent hashing** solves this by placing both servers and keys on a virtual ring (hash space mapped to 0..2^32-1).

```
Consistent Hashing Ring:

          0 / 2^32
            |
     Server C   Server A
        \       /
         \     /
          \   /
    -------ring--------
          /   \
         /     \
        /       \
     Server B   (keys map to the
                 next server clockwise)

Adding Server D between A and B:
- Only keys between A and D get remapped (from B to D)
- All other keys stay on their original server
- Minimal redistribution!
```

**Virtual nodes** improve load balancing: each physical server gets multiple positions on the ring (e.g., 150 virtual nodes per server). This smooths out the distribution and ensures that when a server is removed, its load is spread evenly among the remaining servers rather than being dumped onto one neighbor.

**Real-world use:** Amazon DynamoDB, Apache Cassandra, Memcached (client-side), Nginx upstream consistent hashing, load balancers.

#### Cuckoo Hashing

Standard open addressing degrades as the table fills: a lookup may probe many slots before finding (or failing to find) a key, so worst-case lookup is O(n). **Cuckoo hashing** trades a more expensive insert for a *guaranteed* worst-case **O(1) lookup**. It uses **two hash functions** and (conceptually) two tables. Every key lives in exactly one of two candidate buckets — `h1(key)` or `h2(key)` — so a lookup checks at most two locations, full stop.

```
Cuckoo hashing — key "X" can only ever be in slot h1(X) or slot h2(X):

  Table 1 (via h1)            Table 2 (via h2)
  +----+----+----+----+       +----+----+----+----+
  | A  |    | X  | C  |       |    | B  | D  |    |
  +----+----+----+----+       +----+----+----+----+

  get("X"):  check Table1[h1(X)] -> hit. (Worst case: also check Table2[h2(X)].)
             Never more than 2 reads, regardless of load.
```

The cost is on insert. To insert a key, you place it in `h1(key)`. If that bucket is occupied, you **kick out** the resident key (the "cuckoo" behavior — like a cuckoo chick evicting eggs from the nest) and re-home the evicted key in *its* other bucket, which may evict yet another key, and so on. This eviction chain usually settles quickly, but at high load factors it can enter a **rehash cycle** — keys keep displacing each other without converging. When a cycle (or a length limit) is detected, the table is rebuilt with new hash functions. Because of this, cuckoo hashing is kept at a moderate load factor (~50% for two tables, higher with more hash functions or a small "stash").

```python
# Illustrative insert logic (not production-grade — omits resize/stash):
def cuckoo_insert(t1, t2, h1, h2, key, max_kicks=32):
    for _ in range(max_kicks):
        i = h1(key)
        if t1[i] is None:
            t1[i] = key
            return True
        key, t1[i] = t1[i], key      # kick out resident, take its place
        j = h2(key)                   # try the evicted key in its OTHER bucket
        if t2[j] is None:
            t2[j] = key
            return True
        key, t2[j] = t2[j], key
    return False  # cycle suspected -> caller must rehash with new h1/h2
```

```text
insert "apple"  -> placed in t1[3]
insert "grape"  -> t1[3] full, evict "apple", place "grape"; "apple" -> t2[5]
insert "mango"  -> t1[3] is "grape", evict, place "mango"; "grape" -> t2[1]
...
insert "kiwi"   -> 32 kicks without settling -> returns False (rehash needed)
```

**How to read this output:** Most inserts touch only one or two slots, but the last line is the failure mode that defines cuckoo hashing in practice: a long eviction chain that never finds an empty home. Returning `False` is the signal to rehash the whole table with fresh hash functions. In an interview the key point is the *asymmetry* — you accept occasional expensive inserts (and a capped load factor) to buy a hard ceiling of two reads per lookup, which is why cuckoo hashing shows up where predictable, bounded lookup latency matters (hardware routers, the **cuckoo filter** mentioned later in this chapter, some in-memory caches).

#### Hash Flooding (Algorithmic Complexity Attack)

A hash table's O(1) guarantee is only an *average* over a good hash distribution. If an adversary can make many keys collide into the same bucket, every operation on that bucket degrades to a linear scan: **O(1) collapses to O(n)** (or O(n²) to insert n colliding keys). This is a **hash flooding** or **algorithmic complexity attack**. Any service that builds a dict/set from *untrusted* input is exposed — classically, web frameworks that parse POST form fields or JSON object keys straight into a dictionary. In 2011 this took down major frameworks (PHP, Python, Ruby, Java, Node) with a single small crafted request that pinned a CPU at 100%.

```python
# The attack shape: thousands of distinct keys engineered to share one bucket.
# Parsing them into a dict turns an O(n) operation into O(n^2):
#
#   data = {crafted_key_1: 1, crafted_key_2: 1, ...}   # all collide
#   -> each insert scans the growing collision chain -> request never returns
```

The standard mitigation is a **randomized, keyed hash**: seed the string hash function with a secret random value chosen at process start, so an attacker cannot precompute colliding keys offline. Python enables exactly this by default for `str`/`bytes` hashing (**SipHash** with a per-process random seed). You can observe it:

```python
# Run twice in two SEPARATE processes:
print(hash("attacker-controlled-key"))
```

```console
$ python -c 'print(hash("attacker-controlled-key"))'
-4814886218878000218
$ python -c 'print(hash("attacker-controlled-key"))'
 6921321756752984419
```

**How to read this output:** The *same string* hashes to a *different* value in each process — that randomization is the defense. Because the seed is secret and changes per process, an attacker can no longer construct a set of keys guaranteed to collide. The flip side is the operational gotcha: do **not** rely on `hash()` (or dict iteration order derived from it) being stable across runs — that is why you cannot persist or shard on raw `hash()` values, and why reproducible tests set `PYTHONHASHSEED=0` to pin the seed. (Note the seed protects only hashing of `str`/`bytes`; ints hash to themselves, so integer-keyed dicts are not covered — but integer keys are rarely attacker-shaped.)

> **Common pitfall:** Treating `hash()` as a stable fingerprint — using it as a cache key written to disk, a shard selector, or a value compared across processes. SipHash randomization means it changes every run. Use an explicit, stable hash (`hashlib.sha256`, `zlib.crc32`) for anything that must survive a restart or be consistent across machines.

> **Key Takeaway:** Hash tables provide O(1) average-case operations, making them the backbone of almost every high-performance system. Understanding collision resolution, load factors, and Python's dict internals helps you reason about performance. For distributed systems, consistent hashing is essential knowledge for designing scalable caches and databases.

---

> [!NOTE]
> **Beginner's Mental Model — Trees:**
> Think of a tree like a computer's file system. You start at the "root" folder (e.g., C:\), which contains subfolders, which in turn contain more subfolders or files (leaves). To find a file, you follow a single, branching pathway down from the root, narrowing your search at every folder you open.

### Trees

Consider how you navigate files on your computer. You start at a single top-level folder, like your main drive, and open subfolders to reveal more folders, eventually leading to individual files. This nested structure resembles a tree. In computer science, a tree is a data structure made of nodes connected in a hierarchy. Rather than arranging data in a flat list, trees organize data in parent-child relationships, starting from a single node called the root. By branching outward, trees allow you to discard large portions of irrelevant data at each step of a search, much like clicking through a folder structure instead of scanning every file on your hard drive.

#### Binary Search Tree (BST)

A Binary Search Tree maintains the invariant that for every node, all values in the left subtree are smaller and all values in the right subtree are larger. This enables **O(log n) average** search, insertion, and deletion by halving the search space at each level.

```
Balanced BST:                     Degenerate/Skewed BST:

         30                            10
        /  \                             \
      15    45                           20
     / \   / \                             \
   10  20 35  50                           30
                                             \
 Height: 2 (log2(7) ~ 2.8)                  40
 Search for 20: 30->15->20 (3 steps)          \
                                               50
                                        Height: 4 (n-1)
                                        Search for 50: 5 steps (linear!)
```

The worst case occurs when elements are inserted in sorted order, producing a degenerate tree that behaves like a linked list with O(n) operations.

```python
class BSTNode:
    def __init__(self, key, value=None):
        self.key = key
        self.value = value
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, key, value=None):
        if self.root is None:
            self.root = BSTNode(key, value)
        else:
            self._insert(self.root, key, value)

    def _insert(self, node, key, value):
        if key < node.key:
            if node.left is None:
                node.left = BSTNode(key, value)
            else:
                self._insert(node.left, key, value)
        elif key > node.key:
            if node.right is None:
                node.right = BSTNode(key, value)
            else:
                self._insert(node.right, key, value)
        else:
            node.value = value  # Update existing key

    def search(self, key):
        return self._search(self.root, key)

    def _search(self, node, key):
        if node is None:
            return None
        if key == node.key:
            return node.value
        elif key < node.key:
            return self._search(node.left, key)
        else:
            return self._search(node.right, key)

# Usage
tree = BST()
for item in [30, 15, 45, 10, 20, 35, 50]:
    tree.insert(item, f"value_{item}")
print(tree.search(20))  # "value_20"
print(tree.search(99))  # None
```

#### Self-Balancing BSTs

Self-balancing trees automatically restructure themselves after insertions and deletions to maintain logarithmic height.

**AVL trees** maintain strict balance: for every node, the heights of the left and right subtrees differ by at most 1. They perform rotations (single or double) after each insertion/deletion. Because they are more strictly balanced, AVL trees provide **faster lookups** but **slower insertions/deletions** due to more frequent rotations.

**Red-Black trees** use a coloring scheme (each node is red or black) with relaxed balance rules. They guarantee that the longest path is at most twice the shortest, which means the tree height is at most `2 * log2(n)`. They perform **fewer rotations** on insert/delete (at most 2-3 rotations vs. potentially O(log n) for AVL), making them preferred when writes are frequent. Red-Black trees are used in C++ `std::map`, Java `TreeMap`, and the Linux kernel's CFS scheduler.

```
AVL Rotation Example — Left Rotation:

  Before (right-heavy):           After rotation:

       10                              20
        \                             /  \
        20            =>            10    30
          \
          30

Right Rotation, Left-Right Rotation, and Right-Left Rotation
handle the other imbalance cases.
```

#### B-Trees and B+ Trees

B-Trees are designed for **disk-based storage** systems. Unlike binary trees that have at most 2 children, a B-Tree node can have hundreds or thousands of children (high **branching factor**). This minimizes the number of disk reads needed to find a key because each node read from disk eliminates a large fraction of the search space.

```
B-Tree of order 4 (max 3 keys, max 4 children per node):

                    [  30  |  60  ]
                   /       |       \
          [10 | 20]   [40 | 50]   [70 | 80 | 90]
          /  |  \     /  |  \     /  |   |   \
        ... ... ... ... ... ... ... ... ... ...
        (leaf nodes with actual data pointers)

Each node fits in a single disk page (e.g., 4KB or 16KB).
With a branching factor of 500, a 3-level B-Tree can index
500 * 500 * 500 = 125 million keys with only 3 disk reads!
```

**B+ Trees** are a variant where:

- Internal nodes store only keys (no data), maximizing the branching factor.
- All data resides in the **leaf nodes**.
- Leaf nodes are linked together in a **linked list**, enabling efficient range scans.

B+ Trees are the foundation of virtually all database indexes. PostgreSQL uses B-Trees (actually B+ Tree variant) for its default index type. MySQL InnoDB uses B+ Trees for both primary (clustered) and secondary indexes.

**Real-world example:** When you create an index in Django:

```python
class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=['price']),  # Creates a B-Tree index in the database
            models.Index(fields=['name', 'price']),  # Composite B-Tree index
        ]

# This query uses the B-Tree index on price for efficient range scanning:
# SELECT * FROM product WHERE price BETWEEN 10 AND 50 ORDER BY price;
Product.objects.filter(price__range=(10, 50)).order_by('price')
```

#### Heaps

A heap is a **complete binary tree** stored as an array where the parent-child relationship satisfies the heap property. In a **min-heap**, every parent is smaller than or equal to its children; in a **max-heap**, every parent is larger.

```
Min-Heap as tree:              Min-Heap as array:

         1                     Index: 0  1  2  3  4  5  6
        / \                    Value: 1  3  2  7  8  5  4
       3   2
      / \ / \                  Parent of i:     (i - 1) // 2
     7  8 5  4                 Left child of i:  2*i + 1
                               Right child of i: 2*i + 2
```

The heap provides **O(1)** access to the min (or max) element and **O(log n)** insertion and extraction. Python's `heapq` module implements a min-heap.

```python
import heapq

# Basic heap operations
heap = []
heapq.heappush(heap, 5)
heapq.heappush(heap, 1)
heapq.heappush(heap, 3)
heapq.heappush(heap, 2)

print(heap[0])          # Peek at minimum: 1 (O(1))
print(heapq.heappop(heap))  # Extract minimum: 1 (O(log n))
print(heapq.heappop(heap))  # Next minimum: 2

# Find N largest/smallest efficiently
data = [34, 1, 89, 12, 45, 67, 23, 56, 78, 9]
print(heapq.nlargest(3, data))   # [89, 78, 67]
print(heapq.nsmallest(3, data))  # [1, 9, 12]

# Priority queue for task scheduling
import heapq
from dataclasses import dataclass, field

@dataclass(order=True)
class Task:
    priority: int
    name: str = field(compare=False)
    description: str = field(compare=False, default="")

task_queue = []
heapq.heappush(task_queue, Task(priority=3, name="send_email"))
heapq.heappush(task_queue, Task(priority=1, name="process_payment"))
heapq.heappush(task_queue, Task(priority=2, name="update_inventory"))

# Process tasks in priority order
while task_queue:
    task = heapq.heappop(task_queue)
    print(f"Processing: {task.name} (priority={task.priority})")
# Processing: process_payment (priority=1)
# Processing: update_inventory (priority=2)
# Processing: send_email (priority=3)
```

**Real-world use:** Dijkstra's shortest-path algorithm, task schedulers, median-finding in streams, merge K sorted lists, top-K problems.

#### Trie (Prefix Tree)

A trie stores strings character-by-character along branches of a tree. Lookup time is **O(m)** where m is the length of the key, independent of how many keys are stored.

```
Trie containing: "cat", "car", "card", "dog", "do"

              (root)
             /      \
            c        d
            |        |
            a        o *   <-- "do" ends here
           / \       |
          t*  r*     g *   <-- "dog" ends here
              |
              d *          <-- "card" ends here

  * marks nodes where a complete word ends
```

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.value = None  # Optional: store a value at terminal nodes

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word, value=None):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        node.value = value

    def search(self, word):
        node = self._find_node(word)
        return node is not None and node.is_end_of_word

    def starts_with(self, prefix):
        """Return all words with the given prefix — useful for autocomplete."""
        node = self._find_node(prefix)
        if node is None:
            return []
        results = []
        self._collect_words(node, prefix, results)
        return results

    def _find_node(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def _collect_words(self, node, prefix, results):
        if node.is_end_of_word:
            results.append(prefix)
        for char, child in node.children.items():
            self._collect_words(child, prefix + char, results)

# Autocomplete example
trie = Trie()
for word in ["python", "pyramid", "pytorch", "pyre", "java", "javascript"]:
    trie.insert(word)

print(trie.starts_with("py"))   # ['python', 'pyramid', 'pytorch', 'pyre']
print(trie.starts_with("java")) # ['java', 'javascript']
print(trie.search("python"))    # True
print(trie.search("pyth"))      # False
```

**Real-world use:** Autocomplete/typeahead, IP routing tables (longest prefix match), spell checkers, DNS resolution, phone directories. A **compressed trie (radix tree)** merges single-child chains to save memory — for example, it stores "thon" as one node instead of four.

#### Segment Trees and Fenwick Trees

**Segment trees** answer range queries (sum, min, max over a range) in **O(log n)** while also supporting point updates in O(log n). They are built by recursively dividing the array into halves.

**Fenwick trees (Binary Indexed Trees)** solve the same problem for prefix sums with a simpler implementation and lower constant factor, also in O(log n) per query and update.

```python
class FenwickTree:
    """Binary Indexed Tree for prefix sum queries and point updates."""

    def __init__(self, n):
        self.n = n
        self.tree = [0] * (n + 1)  # 1-indexed

    def update(self, i, delta):
        """Add delta to element at index i (0-indexed)."""
        i += 1  # Convert to 1-indexed
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)  # Move to parent

    def prefix_sum(self, i):
        """Sum of elements from index 0 to i (0-indexed)."""
        i += 1
        total = 0
        while i > 0:
            total += self.tree[i]
            i -= i & (-i)  # Move to predecessor
        return total

    def range_sum(self, left, right):
        """Sum of elements from index left to right (inclusive)."""
        if left == 0:
            return self.prefix_sum(right)
        return self.prefix_sum(right) - self.prefix_sum(left - 1)

# Example: track daily page views, query totals over date ranges
ft = FenwickTree(7)
daily_views = [100, 250, 180, 300, 120, 400, 210]
for i, views in enumerate(daily_views):
    ft.update(i, views)

print(ft.range_sum(0, 6))  # Total views (all days): 1560
print(ft.range_sum(2, 4))  # Views for days 2-4: 600

# Update day 3's views
ft.update(3, 50)  # Add 50 more views to day 3
print(ft.range_sum(2, 4))  # Updated: 650
```

**Real-world use:** Analytics dashboards (sum over date ranges), time-series aggregation, leaderboard ranking, counting inversions.

> **Key Takeaway:** Trees are the most versatile data structure family. BSTs provide ordered data operations, B-Trees power every database index, heaps enable priority queues, and tries enable prefix-based searches. Understanding when to use each tree variant is critical for system design and performance optimization.

---

> [!NOTE]
> **Beginner's Mental Model — Graphs:**
> Imagine a map of cities (nodes) connected by highways (edges). Unlike a tree where there is only one strict parent-child path, a graph has no single root. You can have multiple routes between the same cities, dead ends, and even loops where you end up back where you started.

### Graphs

Think about a map of cities connected by highways, or a network of friends on social media. Unlike a tree, which has a strict top-down structure with no loops, these networks are web-like and can have multiple paths, dead ends, and circular routes. In computer science, we call this structure a graph. A graph consists of points called nodes (representing cities or people) and connections called edges (representing highways or friendships). Because there is no single root or starting point, graphs let us model complex, interconnected systems where any node can connect to any other node, allowing us to solve problems like finding the shortest driving route or recommending mutual friends.

#### Graph Representations

A graph consists of vertices (nodes) and edges (connections). The two primary representations have very different performance characteristics:

```
Example Graph:

    A --- B
    |   / |
    |  /  |
    C --- D

Adjacency List (best for sparse graphs):         Adjacency Matrix (best for dense graphs):
                                                       A    B    C    D
  A: [B, C]                                       A [  0    1    1    0  ]
  B: [A, C, D]                                    B [  1    0    1    1  ]
  C: [A, B, D]                                    C [  1    1    0    1  ]
  D: [B, C]                                       D [  0    1    1    0  ]

Space: O(V + E)                                   Space: O(V^2)
Check if edge exists: O(degree)                   Check if edge exists: O(1)
Iterate neighbors: O(degree)                      Iterate neighbors: O(V)
```

```python
from collections import defaultdict, deque

class Graph:
    """Adjacency list representation of an undirected graph."""

    def __init__(self):
        self.adj = defaultdict(list)

    def add_edge(self, u, v, weight=1):
        self.adj[u].append((v, weight))
        self.adj[v].append((u, weight))

    def bfs(self, start):
        """Breadth-First Search — explores level by level."""
        visited = {start}
        queue = deque([start])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor, _ in self.adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return order

    def dfs(self, start):
        """Depth-First Search — explores as deep as possible first."""
        visited = set()
        order = []

        def _dfs(node):
            visited.add(node)
            order.append(node)
            for neighbor, _ in self.adj[node]:
                if neighbor not in visited:
                    _dfs(neighbor)

        _dfs(start)
        return order

    def shortest_path_bfs(self, start, end):
        """Shortest path in an unweighted graph using BFS."""
        visited = {start}
        queue = deque([(start, [start])])

        while queue:
            node, path = queue.popleft()
            if node == end:
                return path
            for neighbor, _ in self.adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None  # No path exists

# Example usage
g = Graph()
g.add_edge("A", "B")
g.add_edge("A", "C")
g.add_edge("B", "C")
g.add_edge("B", "D")
g.add_edge("C", "D")

print(g.bfs("A"))                    # ['A', 'B', 'C', 'D']
print(g.dfs("A"))                    # ['A', 'B', 'C', 'D'] (order may vary)
print(g.shortest_path_bfs("A", "D")) # ['A', 'B', 'D']
```

#### BFS vs DFS

**BFS (Breadth-First Search)** uses a queue and explores all neighbors at the current depth before moving deeper. It guarantees the **shortest path in unweighted graphs**. Time and space: O(V + E).

```
BFS traversal order from A:

Level 0:  A
Level 1:  B, C          A ---+--- B
Level 2:  D, E          |       / |
                         C      D  E

Queue trace: [A] -> [B,C] -> [C,D] -> [D,E] -> [E] -> []
```

Applications: shortest path in unweighted graphs, social network "degrees of separation," web crawling (breadth-first crawl of pages), level-order tree traversal.

**DFS (Depth-First Search)** uses a stack (or recursion) and explores as far as possible down one path before backtracking. It is the basis for many graph algorithms. Time: O(V + E), Space: O(V) for the recursion stack.

Applications: topological sort, cycle detection, finding connected components, solving mazes, generating permutations/combinations, dependency resolution (e.g., Django migration dependencies).

#### Dijkstra's Algorithm

Dijkstra finds the **shortest path from a source to all other vertices** in a graph with non-negative edge weights. It uses a priority queue (min-heap) to always process the vertex with the smallest known distance next.

```python
import heapq

def dijkstra(graph_adj, start):
    """
    Dijkstra's shortest path algorithm.
    graph_adj: dict of {node: [(neighbor, weight), ...]}
    Returns: dict of {node: shortest_distance}
    """
    distances = {start: 0}
    pq = [(0, start)]  # (distance, node)
    visited = set()

    while pq:
        dist, node = heapq.heappop(pq)

        if node in visited:
            continue
        visited.add(node)

        for neighbor, weight in graph_adj.get(node, []):
            new_dist = dist + weight
            if new_dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_dist
                heapq.heappush(pq, (new_dist, neighbor))

    return distances

# Example: finding shortest routes between cities
city_graph = {
    "NYC": [("Boston", 215), ("DC", 225)],
    "Boston": [("NYC", 215), ("Portland", 108)],
    "DC": [("NYC", 225), ("Atlanta", 640)],
    "Portland": [("Boston", 108)],
    "Atlanta": [("DC", 640), ("Miami", 660)],
    "Miami": [("Atlanta", 660)],
}

distances = dijkstra(city_graph, "NYC")
for city, dist in sorted(distances.items(), key=lambda x: x[1]):
    print(f"  NYC -> {city}: {dist} miles")
# NYC -> NYC: 0 miles
# NYC -> Boston: 215 miles
# NYC -> DC: 225 miles
# NYC -> Portland: 323 miles
# NYC -> Atlanta: 865 miles
# NYC -> Miami: 1525 miles
```

**Bellman-Ford** handles **negative weights** (Dijkstra cannot) and detects negative cycles. It relaxes all edges V-1 times, running in O(VE). Use it for currency arbitrage detection (negative cycle = arbitrage opportunity) or any graph with negative edges.

**A\* Search** extends Dijkstra with a **heuristic function** that estimates the remaining distance to the goal. It expands the node with the smallest `f(n) = g(n) + h(n)` where g(n) is the cost so far and h(n) is the heuristic estimate. With an admissible heuristic (never overestimates), A* finds the optimal path while exploring fewer nodes than Dijkstra. Used in game pathfinding, GPS route planning, and robotics.

#### Topological Sort

A topological sort produces a **linear ordering** of vertices in a Directed Acyclic Graph (DAG) such that for every edge (u, v), u comes before v. It only exists for DAGs — the presence of a cycle makes topological ordering impossible.

```python
from collections import deque, defaultdict

def topological_sort_kahn(graph_adj, all_nodes):
    """
    Kahn's algorithm (BFS-based topological sort).
    graph_adj: dict of {node: [list of nodes it points to]}
    Returns: topologically sorted list, or None if cycle detected
    """
    in_degree = defaultdict(int)
    for node in all_nodes:
        in_degree[node] = 0

    for node in graph_adj:
        for neighbor in graph_adj[node]:
            in_degree[neighbor] += 1

    # Start with all nodes that have no incoming edges
    queue = deque([node for node in all_nodes if in_degree[node] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph_adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(all_nodes):
        return None  # Cycle detected!
    return result

# Example: Django migration dependency resolution
migration_deps = {
    "0001_initial": ["0002_add_user_email"],
    "0002_add_user_email": ["0003_add_profile", "0004_add_orders"],
    "0003_add_profile": ["0005_add_avatar"],
    "0004_add_orders": ["0005_add_avatar"],
    "0005_add_avatar": [],
}
all_migrations = list(migration_deps.keys())
order = topological_sort_kahn(migration_deps, all_migrations)
print("Migration order:", order)
# Migration order: ['0001_initial', '0002_add_user_email', '0003_add_profile',
#                   '0004_add_orders', '0005_add_avatar']
```

**Real-world applications:** Build systems (Make, Bazel), task scheduling, Django migration ordering, package manager dependency resolution, course prerequisite planning, spreadsheet cell evaluation order.

#### Minimum Spanning Tree

A minimum spanning tree (MST) connects all vertices in a weighted undirected graph with the minimum total edge weight and no cycles.

**Kruskal's algorithm** sorts all edges by weight and greedily adds the cheapest edge that does not form a cycle (using Union-Find to detect cycles). Time: O(E log E).

**Prim's algorithm** starts from any vertex and greedily adds the cheapest edge connecting the current tree to a new vertex (using a priority queue). Time: O((V + E) log V).

**Real-world use:** Network cable layout design, clustering (remove the K-1 most expensive edges to get K clusters), circuit board wiring, approximation algorithms for NP-hard problems.

#### Strongly Connected Components

In a directed graph, a **strongly connected component (SCC)** is a maximal set of vertices where every vertex is reachable from every other vertex. **Tarjan's algorithm** and **Kosaraju's algorithm** both find all SCCs in O(V + E).

**Real-world use:** Compiler optimization (identifying groups of mutually recursive functions), social network analysis (finding tightly-knit communities), detecting circular dependencies.

#### DAGs in Practice

Directed Acyclic Graphs appear everywhere in software systems:

- **Apache Airflow** represents data pipeline workflows as DAGs
- **Django migrations** form a DAG of dependencies
- **CI/CD pipelines** model build steps as DAGs (GitHub Actions, GitLab CI)
- **Spreadsheets**: cell dependency graphs are DAGs (or should be — circular references are an error)
- **Neural networks**: computation graphs in TensorFlow/PyTorch are DAGs

> **Key Takeaway:** Graph problems are everywhere in backend engineering: dependency resolution (topological sort), shortest path routing (Dijkstra/A*), network design (MST), and workflow orchestration (DAGs). Master BFS, DFS, Dijkstra, and topological sort — they cover the vast majority of practical graph problems.

---

### Advanced Data Structures

#### Skip List

A skip list is a **probabilistic alternative to balanced BSTs**. It works by maintaining multiple levels of linked lists, where each higher level skips over more elements. On average, it achieves **O(log n)** for search, insert, and delete.

```
Skip List containing [1, 3, 5, 7, 9, 11, 13]:

Level 3:  HEAD --------> 5 ----------------------------> NIL
Level 2:  HEAD --------> 5 ------------> 9 ------------> NIL
Level 1:  HEAD --> 3 --> 5 -----> 7 --> 9 ----> 11 ----> NIL
Level 0:  HEAD -> 1 -> 3 -> 5 -> 7 -> 9 -> 11 -> 13 -> NIL

Searching for 9:
  Level 3: HEAD -> 5 (5 < 9, move right) -> NIL (overshoot, drop down)
  Level 2: 5 -> 9 (found!)
  Only 3 comparisons instead of 5 in a flat list.
```

Each element is "promoted" to a higher level with some probability (typically 0.5). This randomization gives the logarithmic performance without the complexity of rebalancing rotations.

**Real-world use:** Redis sorted sets (ZSET) use skip lists internally, LevelDB and RocksDB use skip lists for their memtable. Skip lists are simpler to implement correctly than red-black trees and are naturally suited for concurrent access (lock-free variants exist).

> [!NOTE]
> **Beginner's Mental Model — Bloom Filters:**
> Imagine a bouncer at a club with a quick checklist. If you aren't on the guest list, the bouncer can tell you immediately: "You are definitely not on the list" (no false negatives). But if you have a common name, the bouncer might say: "You might be on the list, let me call the manager to double-check" (potential false positive). It saves the manager from checking the heavy database binder for every single person.

#### Bloom Filter

Imagine you are a receptionist at a highly secure building, and there is a massive registry book of authorized visitors. Flipping through this thick book to check every single visitor takes a long time and slows down the entry line. To speed things up, you create a quick, simplified checklist on a single sheet of paper using a special marking code. When someone approaches, you check this sheet first. If their code isn't marked, you can say with absolute certainty: "You are definitely not on the guest list." However, because the marking code is simplified, there is a small chance that different names might produce the same markings. If the sheet shows a mark, you must tell the visitor: "You might be on the list; let me double-check the big registry book." This is how a Bloom filter works. It is an incredibly fast, memory-saving tool that tells you whether an item is definitely not in a set, or if it might be in the set, helping you avoid slow database lookups for items that aren't there.

A Bloom filter is a space-efficient **probabilistic data structure** for testing set membership. It can tell you "definitely not in the set" or "probably in the set." **False positives are possible, but false negatives are impossible.**

```
Bloom Filter (bit array of size 10, using 3 hash functions):

Insert "apple":
  h1("apple") = 1, h2("apple") = 4, h3("apple") = 7
  Bit array: [0, 1, 0, 0, 1, 0, 0, 1, 0, 0]

Insert "banana":
  h1("banana") = 0, h2("banana") = 3, h3("banana") = 7
  Bit array: [1, 1, 0, 1, 1, 0, 0, 1, 0, 0]

Query "cherry":
  h1("cherry") = 1, h2("cherry") = 3, h3("cherry") = 9
  Bits at positions 1, 3, 9 = 1, 1, 0
  Position 9 is 0 => "cherry" is DEFINITELY NOT in the set.

Query "grape":
  h1("grape") = 0, h2("grape") = 4, h3("grape") = 7
  Bits at positions 0, 4, 7 = 1, 1, 1
  All bits are 1 => "grape" is PROBABLY in the set (false positive!)
```

```python
import hashlib
import math

class BloomFilter:
    def __init__(self, expected_items, false_positive_rate=0.01):
        # Calculate optimal bit array size and number of hash functions
        self.size = self._optimal_size(expected_items, false_positive_rate)
        self.num_hashes = self._optimal_hashes(self.size, expected_items)
        self.bit_array = [False] * self.size

    @staticmethod
    def _optimal_size(n, p):
        """Optimal bit array size: m = -(n * ln(p)) / (ln(2)^2)"""
        return int(-n * math.log(p) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hashes(m, n):
        """Optimal number of hash functions: k = (m/n) * ln(2)"""
        return max(1, int((m / n) * math.log(2)))

    def _hashes(self, item):
        """Generate k hash values for an item."""
        results = []
        for i in range(self.num_hashes):
            h = hashlib.sha256(f"{item}:{i}".encode()).hexdigest()
            results.append(int(h, 16) % self.size)
        return results

    def add(self, item):
        for pos in self._hashes(item):
            self.bit_array[pos] = True

    def might_contain(self, item):
        """Returns False = definitely not present, True = probably present."""
        return all(self.bit_array[pos] for pos in self._hashes(item))

# Example: avoid unnecessary database queries
bf = BloomFilter(expected_items=100_000, false_positive_rate=0.01)

# Pre-populate with known usernames
existing_usernames = ["alice", "bob", "carol", "dave"]
for username in existing_usernames:
    bf.add(username)

# Check before hitting the database
def is_username_available(username):
    if bf.might_contain(username):
        # Probably exists — must check database to confirm
        # return db_query(username) is None
        return False  # Simplified
    else:
        # Definitely does not exist — no database query needed!
        return True

print(is_username_available("alice"))    # False (correctly detected)
print(is_username_available("zephyr"))   # True  (definitely not in set)
```

**Real-world use:**

- **Databases:** PostgreSQL and Cassandra use Bloom filters to avoid reading SSTables/pages that definitely do not contain the queried key.
- **Web caching:** CDNs use Bloom filters to decide whether to cache a URL (cache on second hit — the Bloom filter tracks first-hit URLs).
- **Spell checkers:** Quick check if a word is in the dictionary before expensive lookup.
- **Network security:** Checking URLs against a malware blocklist.

#### HyperLogLog

HyperLogLog (HLL) estimates the **cardinality (count of distinct elements)** of a set using only ~12KB of memory, regardless of set size. It achieves less than 2% standard error.

The core insight: if you hash elements and count the maximum number of leading zeros in the binary hash, that maximum is related to the logarithm of the number of distinct elements. HLL uses many such counters (buckets) and combines them for accuracy.

```python
# In Redis, HyperLogLog is a first-class data type:
#
# PFADD visitors "user_1" "user_2" "user_3"
# PFADD visitors "user_1" "user_4"  (duplicate "user_1" doesn't affect count)
# PFCOUNT visitors  => 4
#
# Memory: always ~12KB regardless of how many elements are added.
# Compare: storing 10 million unique user IDs in a Set would need ~400MB.

# In Django, you might use it for analytics:
#
# import redis
# r = redis.Redis()
#
# def track_page_view(page_id, user_id):
#     r.pfadd(f"page_visitors:{page_id}", user_id)
#
# def get_unique_visitors(page_id):
#     return r.pfcount(f"page_visitors:{page_id}")
#
# # Count unique visitors across multiple pages:
# r.pfmerge("all_visitors", "page_visitors:home", "page_visitors:about")
# total_unique = r.pfcount("all_visitors")
```

**Real-world use:** Counting unique visitors, unique search queries, unique IP addresses, distinct values in analytics dashboards. Used in Redis (`PFADD`/`PFCOUNT`), Google BigQuery, Apache Flink.

#### LRU Cache

An **LRU (Least Recently Used) cache** evicts the entry that was accessed least recently when the cache is full. It is implemented with a **hash map + doubly-linked list**, giving O(1) for both `get` and `put`.

```
LRU Cache (capacity=3):

  HashMap: {"A": node_A, "B": node_B, "C": node_C}

  Doubly-Linked List (most recent at head):
    HEAD <-> [C] <-> [B] <-> [A] <-> TAIL
              ^                ^
        most recent      least recent
                         (evict this one next)

  Access "B":  move B to head
    HEAD <-> [B] <-> [C] <-> [A] <-> TAIL

  Insert "D" (cache full):  evict A (tail), insert D at head
    HEAD <-> [D] <-> [B] <-> [C] <-> TAIL
```

```python
from functools import lru_cache
from collections import OrderedDict

# Python's built-in LRU cache (for function memoization)
@lru_cache(maxsize=128)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print(fibonacci(100))  # Instant, thanks to memoization
print(fibonacci.cache_info())
# CacheInfo(hits=98, misses=101, maxsize=128, currsize=101)
```

This prints:

```text
354224848179261915075
CacheInfo(hits=98, misses=101, maxsize=128, currsize=101)
```

**How to read this output:** The first line is the 100th Fibonacci number, returned essentially instantly — without memoization, naive recursion would make ~10^21 calls and never finish. The `CacheInfo` line is the real lesson: `misses=101` means each of the 101 distinct `n` values (0 through 100) was computed exactly once, while `hits=98` counts the calls that found their result already cached. That near-1:1 ratio is the signature of a well-memoized recursion turning exponential work into linear. In production, `cache_info()` is how you confirm a cache is actually earning its keep — a high miss rate with low hits usually means your cache key has too much variation (e.g. caching on a timestamp) and the cache is pure overhead.

```python
# Manual LRU Cache implementation using OrderedDict
class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)  # Mark as recently used
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # Evict least recently used

# Django example: caching expensive database queries
cache = LRUCache(capacity=1000)

def get_user_profile(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached
    # Expensive DB query
    # profile = UserProfile.objects.select_related('user').get(user_id=user_id)
    profile = {"user_id": user_id, "name": "Example"}  # Simplified
    cache.put(f"user:{user_id}", profile)
    return profile
```

**LFU (Least Frequently Used) cache** evicts the entry with the lowest access frequency. It is more complex (requiring a frequency counter + hash maps + doubly-linked lists per frequency) but can be more effective when some items are consistently "hot."

> **Common pitfall:** `@lru_cache` holds a strong reference to every cached argument and return value for the life of the process. Decorating an instance method caches `self`, which keeps every instance alive and silently leaks memory; using `maxsize=None` on a function with unbounded inputs grows without limit. Set an explicit `maxsize`, and prefer caching module-level functions over methods.

#### Disjoint Set / Union-Find

Union-Find tracks a collection of non-overlapping sets and supports two operations: `find` (which set does an element belong to?) and `union` (merge two sets). With **path compression** and **union by rank**, both operations run in nearly **O(1) amortized** time (technically O(alpha(n)), where alpha is the inverse Ackermann function, effectively constant).

```python
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n  # Number of disjoint sets

    def find(self, x):
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]

    def union(self, x, y):
        """Union by rank — attach shorter tree under taller tree."""
        root_x, root_y = self.find(x), self.find(y)
        if root_x == root_y:
            return False  # Already in same set
        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x
        self.parent[root_y] = root_x
        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1
        self.count -= 1
        return True

    def connected(self, x, y):
        return self.find(x) == self.find(y)

# Example: Kruskal's MST algorithm
def kruskal_mst(num_vertices, edges):
    """
    edges: list of (weight, u, v)
    Returns: list of MST edges and total weight
    """
    edges.sort()  # Sort by weight
    uf = UnionFind(num_vertices)
    mst = []
    total_weight = 0

    for weight, u, v in edges:
        if uf.union(u, v):  # Only add if it doesn't create a cycle
            mst.append((u, v, weight))
            total_weight += weight
            if len(mst) == num_vertices - 1:
                break  # MST complete

    return mst, total_weight

# Network of servers — find minimum cost to connect them all
edges = [
    (4, 0, 1), (8, 0, 2), (7, 1, 2), (2, 1, 3),
    (6, 2, 3), (1, 3, 4), (3, 2, 4),
]
mst, cost = kruskal_mst(5, edges)
print(f"MST edges: {mst}, Total cost: {cost}")
# MST edges: [(3, 4, 1), (1, 3, 2), (2, 4, 3), (0, 1, 4)], Total cost: 10
```

**Real-world use:** Network connectivity checks, Kruskal's MST, detecting cycles in undirected graphs, image segmentation, social network friend group detection.

#### Other Advanced Structures

**Rope:** A balanced binary tree of strings. Each leaf holds a substring, and each internal node stores the total length of its left subtree. This enables O(log n) insert, delete, and concatenate operations on large strings — vastly superior to O(n) for array-backed strings. Used in text editors (VS Code, Xi editor).

**Count-Min Sketch:** A probabilistic data structure for frequency estimation in streaming data. Like a Bloom filter but for counts instead of membership. Uses multiple hash functions and a 2D array. Estimates are always greater than or equal to the true count (overestimates possible, underestimates impossible). Used in network monitoring (heavy-hitter detection), NLP (approximate word counts), and stream processing.

> **Key Takeaway:** Advanced data structures solve specific problems that general-purpose structures handle poorly. Bloom filters save disk I/O, HyperLogLog counts unique items in constant space, LRU caches speed up repeated lookups, and Union-Find handles dynamic connectivity. You do not need to implement these from scratch in production (use Redis, database features, or well-tested libraries), but understanding how they work helps you choose the right tool and configure it properly.

*Last reviewed: 2026-06-08*
