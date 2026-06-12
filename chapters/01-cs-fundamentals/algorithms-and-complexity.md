[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 1.2 Algorithms & Complexity

> [!NOTE]
> **Beginner's Mental Model — Big-O Analysis:**
> Think of Big-O as choosing a way to travel. If you are going next door, walking is fast. If you are going across the country, walking would take forever, so you need a plane. Big-O doesn't tell you the exact minutes a trip takes; it tells you how much longer the trip gets as the distance (input size `n`) grows. A plane is O(1) overhead time to board, but once in the air, it handles huge distances easily, whereas walking is O(n)—double the distance, double the time.

### Big-O Analysis

Imagine you are planning how to travel to a destination. If your destination is just next door, walking is extremely fast and takes almost no preparation. If you need to travel to another city, walking would take forever, so you might choose to take a flight instead. Boarding a plane requires a lot of overhead—packing, traveling to the airport, and going through security—which might take hours even if the flight itself is short. However, if you are traveling across the entire globe, that fixed boarding time becomes negligible compared to the days or weeks it would take to walk. In computer science, Big-O notation works exactly like comparing travel methods. It does not measure the exact milliseconds a computer takes to run a program. Instead, it describes how the program's running time or memory usage scales as the amount of input data (the distance of your trip) grows larger. It helps you decide whether a particular algorithm is built for a short walk or a cross-country flight.

#### Understanding Complexity Classes

Big-O notation describes how an algorithm's resource usage (time or space) scales with input size. It captures the **growth rate** and ignores constant factors, because at large enough scale, the growth rate dominates.

```
Common complexity classes and their practical impact:

  n          O(1)    O(log n)   O(n)    O(n log n)   O(n^2)     O(2^n)
  --------   -----   --------   -----   ----------   --------   -----------
  10         1       3.3        10      33           100        1,024
  100        1       6.6        100     664          10,000     1.27 x 10^30
  1,000      1       10         1,000   10,000       1,000,000  (heat death)
  1,000,000  1       20         10^6    2 x 10^7     10^12      (heat death)

  As a rule of thumb for competitive programming / interviews:
    - O(n)        => n up to ~10^8  (runs in ~1 second)
    - O(n log n)  => n up to ~10^6-10^7
    - O(n^2)      => n up to ~10^4
    - O(2^n)      => n up to ~20-25
    - O(n!)       => n up to ~10-12
```

```python
# O(1) - Constant: dict lookup, array index access
def get_user(users_dict, user_id):
    return users_dict.get(user_id)  # O(1) average

# O(log n) - Logarithmic: binary search, balanced tree operations
def binary_search(sorted_list, target):
    left, right = 0, len(sorted_list) - 1
    while left <= right:
        mid = (left + right) // 2
        if sorted_list[mid] == target:
            return mid
        elif sorted_list[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# O(n) - Linear: scanning all elements
def find_max(lst):
    max_val = lst[0]
    for item in lst:
        if item > max_val:
            max_val = item
    return max_val

# O(n log n) - Linearithmic: efficient sorting
def sort_and_deduplicate(lst):
    return sorted(set(lst))  # set is O(n), sorted is O(n log n)

# O(n^2) - Quadratic: nested loops over input
def has_duplicate_pair(lst):
    """Naive O(n^2) — better to use a set for O(n)."""
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            if lst[i] == lst[j]:
                return True
    return False

# O(2^n) - Exponential: generating all subsets
def all_subsets(items):
    if not items:
        return [[]]
    rest = all_subsets(items[1:])
    return rest + [[items[0]] + subset for subset in rest]
```

> **Common pitfall:** The `O(1)` average on `dict.get()` and the `O(n log n)` on `sorted()` describe *growth rate*, not wall-clock time. A constant-factor-heavy O(n) pass over a NumPy array can beat a "better" O(log n) pure-Python loop for the n values you actually have. In interviews state the Big-O; in production profile the real input sizes before optimizing.

#### Amortized Analysis

Amortized analysis looks at the **average cost per operation over a sequence**, not the worst case of a single operation. The classic example is Python's `list.append()`:

- Most appends are O(1) because there is room in the pre-allocated buffer.
- Occasionally, the buffer is full and the entire list must be copied to a larger buffer — that single append is O(n).
- But that expensive copy happens only once every ~n appends, so the amortized cost is O(1).

This same principle applies to hash table resizing, Union-Find with path compression, and splay tree operations.

#### Best / Average / Worst Case

Different inputs can cause the same algorithm to perform very differently:

| Algorithm | Best | Average | Worst | Notes |
|---|---|---|---|---|
| Quicksort | O(n log n) | O(n log n) | O(n^2) | Worst case: already sorted + naive pivot |
| Hash lookup | O(1) | O(1) | O(n) | Worst case: all keys collide |
| Binary search | O(1) | O(log n) | O(log n) | Best: target is middle element |
| Insertion sort | O(n) | O(n^2) | O(n^2) | Best: already sorted |

#### Space-Time Tradeoffs

Almost every optimization decision involves trading one resource for another:

- **Caching** (trade space for time): store computed results to avoid recomputation. Django's cache framework, `@lru_cache`, database query caches.
- **Precomputation** (trade startup time for query time): build indexes, lookup tables, or suffix arrays once, then answer queries quickly. Database indexes trade write speed and disk space for read speed.
- **Streaming algorithms** (trade accuracy for space): HyperLogLog, Count-Min Sketch, reservoir sampling — process data in one pass with bounded memory at the cost of approximate answers.
- **Compression** (trade CPU time for space/bandwidth): gzip responses, compressed database pages — CPU decompresses on read.

#### Master Theorem

For divide-and-conquer recurrences of the form **T(n) = aT(n/b) + O(n^d)**:

- If d > log_b(a): T(n) = O(n^d)
- If d = log_b(a): T(n) = O(n^d * log n)
- If d < log_b(a): T(n) = O(n^(log_b(a)))

```
Examples:
  Binary Search:  T(n) = 1*T(n/2) + O(1)   => a=1, b=2, d=0 => O(log n)
  Merge Sort:     T(n) = 2*T(n/2) + O(n)   => a=2, b=2, d=1 => O(n log n)
  Strassen:       T(n) = 7*T(n/2) + O(n^2) => a=7, b=2, d=2 => O(n^2.807)
```

> **Key Takeaway:** Big-O analysis is not about memorizing formulas — it is about developing the intuition to look at code and immediately recognize its scaling behavior. When evaluating a solution in production, always consider: What is n? How large will it get? What are the constant factors? And remember that Big-O is an upper bound on growth rate; the actual performance depends on constants, cache behavior, and real-world data distribution.

---

### Algorithmic Techniques (Problem-Solving Patterns)

Most interview problems — and a surprising amount of real backend code — are instances of a handful of recurring patterns. Recognizing the pattern is the whole battle; the implementation usually follows mechanically.

#### Two Pointers

Walk a sequence with two indices instead of nesting two loops. The classic uses: find a pair summing to a target in a **sorted** array, remove duplicates in place, partition, or check a palindrome. Moving the pointers based on the current comparison collapses an O(n²) brute force into a single **O(n)** pass.

```python
def two_sum_sorted(nums, target):
    """Find indices of two numbers that sum to target. Array must be sorted."""
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        s = nums[lo] + nums[hi]
        if s == target:
            return (lo, hi)
        if s < target:
            lo += 1      # need a bigger sum -> move left pointer up
        else:
            hi -= 1      # need a smaller sum -> move right pointer down
    return None

print(two_sum_sorted([1, 3, 4, 6, 8, 11], 10))  # (2, 3)  -> 4 + 6
```

The key insight: because the array is sorted, each comparison lets you *discard* a whole side, so each element is visited at most once.

#### Sliding Window

A sliding window maintains a contiguous range `[left, right)` over a sequence and answers a question about "the best/longest/shortest subarray satisfying a constraint." There are two flavors:

- **Fixed window:** the size `k` is given (e.g., max sum of any 5 consecutive elements). Slide by adding the new element and subtracting the one that fell off — O(n) instead of O(n·k).
- **Variable window:** the window grows and shrinks to satisfy a constraint (e.g., longest substring with no repeated characters). Expand `right` to include more; when the constraint breaks, advance `left` until it holds again.

```python
def longest_unique_substring(s):
    """Length of the longest substring without repeating characters (variable window)."""
    seen = {}            # char -> last index
    left = best = 0
    for right, ch in enumerate(s):
        if ch in seen and seen[ch] >= left:
            left = seen[ch] + 1   # shrink window past the previous occurrence
        seen[ch] = right
        best = max(best, right - left + 1)
    return best

print(longest_unique_substring("abcabcbb"))  # 3  ("abc")
print(longest_unique_substring("bbbbb"))      # 1  ("b")
```

```text
3
1
```

**How to read this output:** Each character is added once (by `right`) and removed at most once (by advancing `left`), so the whole scan is O(n) even though it *feels* like it re-examines characters. This is the exact structure behind **rate-limiting sliding windows** and **time-windowed aggregations** in backend systems: you keep a running window over a stream and update it incrementally instead of recomputing from scratch on every event.

#### Binary Search on the Answer

Binary search is not only for searching a sorted array. When a problem asks "what is the minimum/maximum X that works?" and the predicate `works(X)` is **monotonic** (if `X` works, every larger X works — or vice versa), you can binary-search over the *answer space* and call `works()` as the comparison. This turns "try every possible value" into O(log(range) · cost-of-check).

```python
def min_capacity_to_ship(weights, days):
    """Smallest daily ship capacity that delivers all packages within `days`."""
    def feasible(cap):
        needed, load = 1, 0
        for w in weights:
            if load + w > cap:
                needed += 1      # start a new day
                load = 0
            load += w
        return needed <= days

    lo, hi = max(weights), sum(weights)   # answer is somewhere in this range
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(mid):
            hi = mid            # mid works -> maybe a smaller cap also works
        else:
            lo = mid + 1        # mid too small -> need more capacity
    return lo

print(min_capacity_to_ship([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], days=5))  # 15
```

This pattern shows up directly in **capacity planning** ("smallest instance size that meets the SLA"), **allocation** ("minimize the maximum load on any worker"), and rate/quota tuning.

#### Backtracking

Backtracking builds a solution incrementally and **abandons (prunes)** any partial candidate the moment it cannot possibly succeed. It is depth-first search over the space of choices. Permutations, combinations, subsets, N-queens, Sudoku, and constraint-satisfaction problems are all backtracking.

```python
def permutations(items):
    result = []
    def backtrack(current, remaining):
        if not remaining:
            result.append(current[:])
            return
        for i in range(len(remaining)):
            current.append(remaining[i])
            backtrack(current, remaining[:i] + remaining[i+1:])
            current.pop()       # undo the choice — the "backtrack" step
    backtrack([], items)
    return result

print(permutations([1, 2, 3]))
# [[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]
```

The `current.pop()` is the heart of the technique: after exploring a branch, you undo the choice so the parent frame can try the next one. Effective backtracking lives or dies on **pruning** — the earlier you can reject a doomed partial solution, the smaller the search tree.

#### Greedy

A greedy algorithm makes the **locally optimal choice** at each step and never reconsiders. It is correct only when the problem has the **greedy-choice property** (a global optimum can be reached by local choices) plus optimal substructure. Interval scheduling (always pick the earliest-finishing compatible interval), Huffman coding, and Dijkstra are greedy and provably correct.

```python
def max_non_overlapping(intervals):
    """Maximum number of non-overlapping intervals (activity selection)."""
    intervals.sort(key=lambda iv: iv[1])   # sort by END time — the greedy key
    count, last_end = 0, float('-inf')
    for start, end in intervals:
        if start >= last_end:
            count += 1
            last_end = end
    return count

print(max_non_overlapping([(1, 3), (2, 5), (4, 7), (6, 8)]))  # 2  -> picks (1,3) and (4,7)
```

> **Common pitfall:** Greedy *feels* right far more often than it *is* right. Sorting by start time (instead of end time) above gives a wrong answer; many "obvious" greedy strategies fail on adversarial inputs. Before trusting a greedy solution, either prove the greedy-choice property or test it against a brute-force/DP solution on random inputs — a silently-wrong greedy is a classic production bug.

#### Divide and Conquer

Split the problem into independent subproblems, solve them recursively, and combine the results. Merge sort, quickselect, FFT, and Karatsuba multiplication are all divide-and-conquer; their running times come straight from the Master Theorem above. The pattern parallelizes naturally because the subproblems are independent (map-reduce is divide-and-conquer at cluster scale).

#### Bit Manipulation

Treating integers as bitsets enables compact flags and constant-time tricks that are common in low-level/high-performance code:

```python
x = 0b101100

x & (x - 1)     # 0b101000 — clears the LOWEST set bit
x & -x          # 0b000100 — isolates the LOWEST set bit
x | (1 << 3)    # set bit 3
x & ~(1 << 2)   # clear bit 2
bin(x).count("1")  # popcount — number of set bits (Python 3.10+: x.bit_count())

# XOR trick: find the single element that appears once when all others appear twice
def single_number(nums):
    result = 0
    for n in nums:
        result ^= n     # pairs cancel (a ^ a == 0); the lone value survives
    return result

print(single_number([4, 1, 2, 1, 2]))  # 4
```

```text
4
```

**How to read this output:** The XOR scan finds the unpaired number in a single O(n) pass with O(1) memory — no hash set needed — because `a ^ a == 0` and XOR is commutative, so every duplicated value cancels itself out and only the singleton remains. Bit tricks like this and `x & (x-1)` are the backbone of **permission/flag fields** (a single integer column encoding many booleans), **bitset-based filters**, and compact data structures where memory and cache footprint dominate.

> **Key Takeaway:** Internalize the trigger words. "Pair / sorted array" → two pointers. "Longest/shortest contiguous … window" → sliding window. "Minimum X such that …" with a monotonic check → binary search on the answer. "All combinations / valid configurations" → backtracking. "Pick the best at each step" → greedy (but verify it). Pattern recognition is what turns a 30-minute interview problem into a 5-minute one, and it is exactly how experienced engineers map a fuzzy product requirement onto a known algorithm.

---

> [!NOTE]
> **Beginner's Mental Model — Sorting:**
> Imagine sorting a messy pile of student exams by last name. You could split the pile in half, hand each half to an assistant to sort, and then merge their two sorted stacks together (Merge Sort). Alternatively, you could pick one exam as a benchmark, put all names before it on the left and all names after it on the right, and repeat the process on those smaller piles (Quicksort).

### Sorting

Imagine you are handed a giant, messy stack of student exams and asked to sort them alphabetically by last name. One approach is to divide the stack in half, hand each half to an assistant to sort, and then combine the two sorted piles by looking at the top sheet of each pile and placing the alphabetically earlier name into a new single pile (this is the merge sort strategy). Another approach is to pick a random exam from the stack as a benchmark, put all exams with names earlier than the benchmark on the left, all exams with later names on the right, and then repeat this process on the smaller piles until the whole stack is sorted (this is the quicksort strategy). Sorting algorithms are simply different strategies for putting items in order. Depending on the size of the stack, the amount of workspace you have, and whether you are sorting physical papers or virtual database records, choosing the right strategy can mean the difference between a few minutes of work and a few hours.

#### Comparison-Based Sorts

All comparison-based sorting algorithms have a theoretical lower bound of **Omega(n log n)** — you cannot do better if your only operation is comparing two elements. The three main comparison sorts each have different strengths:

```
Quicksort partitioning example (Lomuto partition, pivot = last element):

  [8, 3, 5, 1, 9, 2, 7]    pivot = 7
   ^                   ^
  Start partitioning: elements <= 7 go left, > 7 go right

  [3, 5, 1, 2, 7, 9, 8]    After partition
               ^
            pivot in correct position

  Now recursively sort [3, 5, 1, 2] and [9, 8]
```

**Quicksort** is the most widely used general-purpose sort. It partitions the array around a pivot element and recursively sorts the two halves. It is **in-place** (O(log n) stack space), has excellent **cache locality** because it works on contiguous memory, and averages O(n log n). The weakness is O(n^2) worst case when the pivot consistently picks the smallest or largest element — mitigated by randomized pivot selection or median-of-three.

**Merge Sort** divides the array in half, recursively sorts both halves, and merges them. It guarantees **O(n log n) in all cases** and is **stable** (preserves relative order of equal elements). The downside is it requires **O(n) extra space** for the merge step. Merge sort is the algorithm of choice for sorting linked lists (no random access needed) and for external sorting (sorting data larger than RAM).

**Heap Sort** builds a max-heap from the array and repeatedly extracts the maximum. It is **in-place** and guarantees O(n log n), but has **poor cache locality** (jumps around the array following heap parent-child relationships), making it slower in practice than quicksort.

```python
def quicksort(arr):
    """In-place quicksort with random pivot."""
    import random

    def _sort(lo, hi):
        if lo >= hi:
            return
        # Random pivot to avoid worst case on sorted input
        pivot_idx = random.randint(lo, hi)
        arr[pivot_idx], arr[hi] = arr[hi], arr[pivot_idx]
        pivot = arr[hi]

        i = lo
        for j in range(lo, hi):
            if arr[j] <= pivot:
                arr[i], arr[j] = arr[j], arr[i]
                i += 1
        arr[i], arr[hi] = arr[hi], arr[i]
        _sort(lo, i - 1)
        _sort(i + 1, hi)

    _sort(0, len(arr) - 1)
    return arr

def merge_sort(arr):
    """Stable O(n log n) sort with O(n) extra space."""
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    # Merge two sorted halves
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:  # <= ensures stability
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
```

> **Common pitfall:** This recursive `quicksort` recurses to a depth of O(log n) on average, but a naive (non-random) pivot on already-sorted input recurses n deep and hits Python's default recursion limit (1000) — a `RecursionError` in production on the very input people forget to test. Random pivots fix the average case; an explicit stack or `sys.setrecursionlimit` is needed only if you must guarantee it.

#### Non-Comparison Sorts

When keys are integers (or can be mapped to integers) within a known range, non-comparison sorts can beat the O(n log n) barrier:

**Counting Sort** counts occurrences of each value, then reconstructs the sorted array. Time: O(n + k) where k is the range of values. Only practical when k is not much larger than n.

**Radix Sort** sorts by each digit (or byte) from least significant to most significant, using a stable sort (like counting sort) for each digit pass. Time: O(d * (n + k)) where d is the number of digits and k is the digit range (10 for decimal, 256 for byte-level). Great for sorting fixed-length strings, IP addresses, or integers.

**Bucket Sort** distributes elements into buckets based on value ranges, sorts each bucket individually, then concatenates. Average O(n) when input is uniformly distributed.

```python
def counting_sort(arr, max_val):
    """Sort non-negative integers in O(n + k) time."""
    count = [0] * (max_val + 1)
    for x in arr:
        count[x] += 1

    result = []
    for val, cnt in enumerate(count):
        result.extend([val] * cnt)
    return result

def radix_sort(arr):
    """Sort non-negative integers by processing each digit."""
    if not arr:
        return arr
    max_val = max(arr)
    exp = 1
    while max_val // exp > 0:
        # Stable counting sort on current digit
        output = [0] * len(arr)
        count = [0] * 10
        for x in arr:
            digit = (x // exp) % 10
            count[digit] += 1
        for i in range(1, 10):
            count[i] += count[i - 1]
        for x in reversed(arr):  # Traverse in reverse for stability
            digit = (x // exp) % 10
            count[digit] -= 1
            output[count[digit]] = x
        arr = output
        exp *= 10
    return arr

print(radix_sort([170, 45, 75, 90, 802, 24, 2, 66]))
# [2, 24, 45, 66, 75, 90, 170, 802]
```

**How to read this output:** The numbers come out fully sorted even though each pass only looks at one digit. That only works because the per-digit counting sort is *stable* — after sorting on the ones digit, the tens-digit pass preserves the ones-digit order for ties, and so on. Break stability (e.g. iterate `arr` forward instead of `reversed`) and the result is silently wrong, which is exactly the kind of bug that passes small tests and corrupts a production sort of fixed-width keys like timestamps or zero-padded IDs.

#### Stability in Sorting

A sort is **stable** if it preserves the relative order of elements with equal keys. This matters when sorting by multiple criteria:

```python
# Sort employees first by department (primary), then by salary (secondary)
employees = [
    ("Engineering", 120000, "Alice"),
    ("Marketing",    90000, "Bob"),
    ("Engineering", 100000, "Carol"),
    ("Marketing",    95000, "Dave"),
]

# With a stable sort, we can sort by secondary key first, then primary key
# Python's sort is stable (Timsort), so this works:
employees.sort(key=lambda e: e[1])        # Sort by salary
employees.sort(key=lambda e: e[0])        # Sort by department (stable!)
# Result: Engineering(100K Carol), Engineering(120K Alice), Marketing(90K Bob), Marketing(95K Dave)
# Within each department, salary order is preserved because the sort is stable.

# Or use a tuple key for multi-criteria sorting in one pass:
employees.sort(key=lambda e: (e[0], e[1]))
```

#### Python's Timsort

Python uses **Timsort**, a hybrid of merge sort and insertion sort. It identifies naturally occurring "runs" (already sorted subsequences), extends short runs using insertion sort, then merges runs using a modified merge sort. Timsort is **stable**, **adaptive** (faster on partially sorted data), and guarantees **O(n log n) worst case**.

```python
# sorted() returns a new list; .sort() sorts in-place
data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]
sorted_data = sorted(data)        # New list: [1, 1, 2, 3, 3, 4, 5, 5, 6, 9]
data.sort()                        # In-place modification

# Custom key functions
words = ["banana", "apple", "cherry", "date"]
sorted(words, key=len)             # Sort by length: ['date', 'apple', 'banana', 'cherry']
sorted(words, key=str.lower)       # Case-insensitive sort

# Django QuerySet ordering (happens in the database, not Python)
# Product.objects.order_by('price')              # ASC
# Product.objects.order_by('-price')             # DESC
# Product.objects.order_by('category', 'price')  # Multi-key
```

#### External Sorting

When data is too large to fit in RAM, **external sorting** uses a merge sort variant:

1. Read chunks that fit in memory, sort each chunk (using quicksort or Timsort), write sorted chunks to disk.
2. Merge all sorted chunks using a K-way merge (priority queue reads the smallest element from each chunk).

This is the technique used by database query processors for `ORDER BY` on large result sets, and by Unix `sort` command for large files.

> **Key Takeaway:** For almost all Python work, use the built-in `sorted()` or `.sort()` — Timsort is an excellent general-purpose sort. Know the properties of each algorithm (stability, space, worst case) so you can reason about performance and understand database query plan choices. Non-comparison sorts are important for specialized high-throughput scenarios like sorting log entries by timestamp or IP addresses.

---

### Selection & Order Statistics

Often you do not need a fully sorted array — you need *one* element by rank (the median, the 95th percentile) or the *top few*. Fully sorting is O(n log n); these problems can be solved faster.

#### Quickselect

Quickselect finds the **k-th smallest element in O(n) average time**. It uses quicksort's partition step, but instead of recursing into both halves, it recurses only into the side that contains rank `k`. Each step discards (on average) half the array, giving the linear average cost — though, like quicksort, a bad pivot gives O(n²) worst case (a random pivot avoids it in practice).

```python
import random

def quickselect(arr, k):
    """Return the k-th smallest element (0-indexed) in O(n) average time."""
    if not 0 <= k < len(arr):
        raise IndexError("k out of range")
    arr = arr[:]                      # don't mutate caller's list
    lo, hi = 0, len(arr) - 1
    while True:
        pivot = arr[random.randint(lo, hi)]
        # 3-way partition: < pivot | == pivot | > pivot
        lt, gt, i = lo, hi, lo
        while i <= gt:
            if arr[i] < pivot:
                arr[lt], arr[i] = arr[i], arr[lt]; lt += 1; i += 1
            elif arr[i] > pivot:
                arr[gt], arr[i] = arr[i], arr[gt]; gt -= 1
            else:
                i += 1
        if k < lt:
            hi = lt - 1               # k is in the "< pivot" region
        elif k > gt:
            lo = gt + 1               # k is in the "> pivot" region
        else:
            return arr[k]             # k landed in the "== pivot" region -> done

data = [7, 2, 9, 4, 1, 8, 5, 3, 6]
print(quickselect(data, 0))  # 1  (smallest)
print(quickselect(data, 4))  # 5  (median of 9 elements)
print(quickselect(data, 8))  # 9  (largest)
```

```text
1
5
9
```

**How to read this output:** Each call returns the element that *would* sit at index `k` if the array were sorted, without ever fully sorting it. The win is real when you need a percentile or median once: O(n) average versus O(n log n) for a full sort. The catch — and a good interview point — is the worst case: on adversarial input a fixed pivot degrades to O(n²), which is why the randomized pivot above (or the median-of-medians variant for a *guaranteed* O(n)) matters in any code path an attacker can feed.

#### Heap-Based Top-K

When you want the **k largest (or smallest) of n** items and `k ≪ n` — or the data is a *stream* you cannot fully hold — maintain a size-`k` heap. Each item costs O(log k) to consider, giving **O(n log k)** total, which beats sorting (O(n log n)) when k is small and uses only O(k) memory.

```python
import heapq

stream = [34, 1, 89, 12, 45, 67, 23, 56, 78, 9]

# Top-3 largest. heapq.nlargest does exactly the size-k heap trick internally.
print(heapq.nlargest(3, stream))   # [89, 78, 67]
print(heapq.nsmallest(3, stream))  # [1, 9, 12]

# Streaming top-k with a bounded MIN-heap of size k:
def top_k_stream(stream, k):
    heap = []                          # min-heap; smallest of the top-k sits at root
    for x in stream:
        if len(heap) < k:
            heapq.heappush(heap, x)
        elif x > heap[0]:              # bigger than the current weakest survivor?
            heapq.heapreplace(heap, x) # pop smallest, push x — O(log k)
    return sorted(heap, reverse=True)

print(top_k_stream(stream, 3))         # [89, 78, 67]
```

```text
[89, 78, 67]
[1, 9, 12]
[89, 78, 67]
```

**How to read this output:** All three approaches agree, but the streaming version is the one that scales: it never holds more than `k` elements in memory, so it works on an unbounded stream (top-100 trending products from a firehose of events, top-N slowest queries from a log tail). The trick is the **min**-heap for the **largest** k — the root is the weakest member of the current winners, so a new item only needs one O(log k) comparison to decide if it earns a spot. Reaching for a full sort here, or for `nlargest` over a materialized list, would force you to buffer the entire stream.

> **Key Takeaway:** Match the tool to the need. One percentile/median from a list → quickselect (O(n)). Top-k from a large or streaming dataset → a size-k heap / `heapq.nlargest` (O(n log k), O(k) memory). Reserve a full sort for when you genuinely need *all* elements ordered — paying O(n log n) to read off one element or a handful is a common, avoidable inefficiency.

---

> [!NOTE]
> **Beginner's Mental Model — Dynamic Programming:**
> Imagine I write `1 + 1 + 1 + 1 + 1` on a board and ask you what it equals. You count them up and say "5". If I write another `+ 1` at the end, you don't recount all the ones from the beginning. You remember that the first part was "5" and simply add 1 to get "6". Dynamic Programming is just that: writing down the answers to sub-problems so you never have to recalculate them.

### Dynamic Programming

Suppose someone writes the equation 1 + 1 + 1 + 1 + 1 on a chalkboard and asks you for the sum. You count the ones and answer "five." If the person then writes another + 1 at the end of the line and asks for the new total, you do not start over and count the ones from the beginning. Instead, you remember that the previous part summed to five, and you simply add one to that stored result to get "six." This concept of remembering past calculations to save work on future ones is the core of dynamic programming. In programming, many complex problems can be broken down into smaller, repetitive sub-problems. Rather than solving the exact same sub-problem over and over again—which wastes valuable computer processing power—dynamic programming writes down the answers to those sub-problems the first time they are solved and looks them up whenever they are needed again.

#### Core Concepts

Dynamic programming (DP) applies when a problem has two properties:

1. **Overlapping subproblems**: the same subproblems are solved multiple times in a naive recursive approach.
2. **Optimal substructure**: the optimal solution to the problem can be constructed from optimal solutions to its subproblems.

There are two approaches:

**Top-down (memoization)**: Write the natural recursive solution, then add a cache to avoid recomputing. This is often easier to write and only computes subproblems that are actually needed.

**Bottom-up (tabulation)**: Build a table iteratively, starting from the smallest subproblems. This avoids recursion overhead and makes it easier to optimize space.

```python
# Example: Fibonacci — the "hello world" of DP

# Naive recursive: O(2^n) — exponential! Recomputes the same values many times.
def fib_naive(n):
    if n < 2:
        return n
    return fib_naive(n - 1) + fib_naive(n - 2)

# Top-down with memoization: O(n) time, O(n) space
from functools import lru_cache

@lru_cache(maxsize=None)
def fib_memo(n):
    if n < 2:
        return n
    return fib_memo(n - 1) + fib_memo(n - 2)

# Bottom-up tabulation: O(n) time, O(n) space
def fib_tab(n):
    if n < 2:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]

# Bottom-up with space optimization: O(n) time, O(1) space
def fib_optimized(n):
    if n < 2:
        return n
    prev2, prev1 = 0, 1
    for _ in range(2, n + 1):
        prev2, prev1 = prev1, prev2 + prev1
    return prev1
```

> **Common pitfall:** `@lru_cache` keys on the *arguments*, so it only works when every argument is hashable. Decorate a function that takes a `list` or `dict` (a common DP setup like `solve(grid, i, j)`) and you get `TypeError: unhashable type: 'list'`. Convert mutable state to a `tuple` first, or carry it via indices/closure instead of arguments. Also note the cache is process-global and never evicts with `maxsize=None` — a memory leak if keyed on unbounded user input.

#### Classic DP Patterns

**0/1 Knapsack** — given items with weights and values, maximize value within a weight capacity:

```python
def knapsack(weights, values, capacity):
    """
    0/1 Knapsack: each item can be taken at most once.
    Time: O(n * capacity), Space: O(n * capacity)
    """
    n = len(weights)
    # dp[i][w] = max value using first i items with capacity w
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]  # Don't take item i
            if weights[i - 1] <= w:
                dp[i][w] = max(
                    dp[i][w],
                    dp[i - 1][w - weights[i - 1]] + values[i - 1]  # Take item i
                )

    return dp[n][capacity]

# Example: server resource allocation
# Items: processes with memory requirements and priority scores
weights = [2, 3, 4, 5]     # Memory (GB)
values  = [3, 4, 5, 6]     # Priority score
capacity = 8                 # Total available memory (GB)
print(knapsack(weights, values, capacity))  # 10 (items with weights 3+5 or 4+2+...)
```

**Edit Distance (Levenshtein Distance)** — minimum operations (insert, delete, replace) to transform one string into another:

```python
def edit_distance(s1, s2):
    """
    Minimum edit distance between two strings.
    Used in: spell checkers, DNA alignment, diff algorithms, fuzzy search.
    Time: O(m * n), Space: O(m * n), can be optimized to O(min(m, n))
    """
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Base cases: transforming to/from empty string
    for i in range(m + 1):
        dp[i][0] = i  # Delete all characters
    for j in range(n + 1):
        dp[0][j] = j  # Insert all characters

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]  # Characters match, no operation needed
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # Delete from s1
                    dp[i][j - 1],      # Insert into s1
                    dp[i - 1][j - 1],  # Replace in s1
                )

    return dp[m][n]

print(edit_distance("kitten", "sitting"))  # 3 (k->s, e->i, +g)
print(edit_distance("django", "flask"))    # 5

# Real-world: fuzzy search for user queries
def fuzzy_match(query, candidates, max_distance=2):
    """Find candidates within edit distance of query."""
    results = []
    for candidate in candidates:
        dist = edit_distance(query.lower(), candidate.lower())
        if dist <= max_distance:
            results.append((candidate, dist))
    return sorted(results, key=lambda x: x[1])

products = ["iPhone", "iPad", "iPod", "MacBook", "iMac"]
print(fuzzy_match("iPone", products))  # [('iPhone', 1), ('iPod', 2)]
```

**Coin Change** — minimum coins to make a given amount:

```python
def coin_change(coins, amount):
    """
    Minimum number of coins to make the given amount.
    Time: O(amount * len(coins)), Space: O(amount)
    """
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0

    for i in range(1, amount + 1):
        for coin in coins:
            if coin <= i and dp[i - coin] + 1 < dp[i]:
                dp[i] = dp[i - coin] + 1

    return dp[amount] if dp[amount] != float('inf') else -1

print(coin_change([1, 5, 10, 25], 63))  # 6 (25+25+10+1+1+1)
```

#### State Machine DP

Some problems are best modeled as transitions between states:

```python
def max_profit_with_cooldown(prices):
    """
    Stock trading: buy, sell, then must wait one day (cooldown).
    States: HOLD (holding stock), SOLD (just sold), REST (cooldown/idle)

    Transitions:
      HOLD -> HOLD (do nothing) or SOLD (sell)
      SOLD -> REST (mandatory cooldown)
      REST -> REST (do nothing) or HOLD (buy)
    """
    if not prices:
        return 0

    hold = -prices[0]  # Bought on day 0
    sold = 0            # Cannot sell on day 0
    rest = 0            # Doing nothing

    for price in prices[1:]:
        prev_hold, prev_sold, prev_rest = hold, sold, rest
        hold = max(prev_hold, prev_rest - price)  # Keep holding or buy from rest
        sold = prev_hold + price                    # Sell what we hold
        rest = max(prev_rest, prev_sold)            # Stay resting or cooldown from sold

    return max(sold, rest)

prices = [1, 2, 3, 0, 2]
print(max_profit_with_cooldown(prices))  # 3 (buy@1, sell@3, cooldown, buy@0, sell@2)
```

#### Bitmask DP

For problems involving subsets of a small set (n <= 20), represent each subset as a bitmask:

```python
def tsp(dist):
    """
    Traveling Salesman Problem using bitmask DP.
    dist[i][j] = distance from city i to city j
    Time: O(n^2 * 2^n), Space: O(n * 2^n)
    """
    n = len(dist)
    ALL_VISITED = (1 << n) - 1  # All bits set
    # dp[mask][i] = min cost to visit all cities in mask, ending at city i
    dp = [[float('inf')] * n for _ in range(1 << n)]
    dp[1][0] = 0  # Start at city 0, only city 0 visited

    for mask in range(1 << n):
        for u in range(n):
            if dp[mask][u] == float('inf'):
                continue
            if not (mask & (1 << u)):
                continue
            for v in range(n):
                if mask & (1 << v):
                    continue  # Already visited
                new_mask = mask | (1 << v)
                new_cost = dp[mask][u] + dist[u][v]
                if new_cost < dp[new_mask][v]:
                    dp[new_mask][v] = new_cost

    # Return to start city
    return min(dp[ALL_VISITED][i] + dist[i][0] for i in range(n))

# Example with 4 cities
dist = [
    [0, 10, 15, 20],
    [10, 0, 35, 25],
    [15, 35, 0, 30],
    [20, 25, 30, 0],
]
print(tsp(dist))  # 80 (0->1->3->2->0)
```

**Practical DP applications in backend systems:**

- Rate limiting with sliding windows
- Resource allocation in cloud scheduling
- Route optimization in delivery systems
- Text wrapping / line-breaking algorithms (Knuth-Plass)
- Diff algorithms (longest common subsequence)

> **Key Takeaway:** Dynamic programming is a thinking technique, not an algorithm. The hard part is identifying the state, the transitions, and the base cases. Start with brute-force recursion, add memoization, then optimize to bottom-up if needed. In backend work, DP appears in diff algorithms, text processing, resource allocation, and optimization problems.

---

### Graph Algorithms (Extended)

#### Floyd-Warshall

Floyd-Warshall computes the **shortest paths between all pairs of vertices** in O(V^3). It works by iteratively considering whether going through an intermediate vertex k gives a shorter path between any pair (i, j).

```python
def floyd_warshall(n, edges):
    """
    All-pairs shortest path.
    n: number of vertices (0-indexed)
    edges: list of (u, v, weight)
    Returns: distance matrix, or detects negative cycles
    """
    INF = float('inf')
    dist = [[INF] * n for _ in range(n)]

    for i in range(n):
        dist[i][i] = 0
    for u, v, w in edges:
        dist[u][v] = w

    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]

    # Check for negative cycles (diagonal becomes negative)
    for i in range(n):
        if dist[i][i] < 0:
            raise ValueError("Negative cycle detected")

    return dist
```

> **Common pitfall:** This implementation uses Python's `float('inf')`, where `inf + inf == inf` stays well-behaved. Port the same triple loop to C/Java/Go with a large sentinel like `INT_MAX` and `dist[i][k] + dist[k][j]` overflows to a *negative* number, which then looks shorter than the real path and silently corrupts the matrix. Use a sentinel no larger than `MAX/2`, or skip the relaxation when either operand is the sentinel.

Best suited for **small, dense graphs** (V < ~500) where you need all pairs of shortest paths, such as computing distances between all pairs of data centers.

#### Network Flow

**Ford-Fulkerson / Edmonds-Karp** solves the maximum flow problem: given a network with source, sink, and edge capacities, find the maximum flow from source to sink.

Applications: maximum bipartite matching (assigning workers to tasks), project selection (choosing projects with dependencies), image segmentation, network bandwidth optimization.

#### Eulerian Paths

An **Eulerian path** visits every edge exactly once. It exists if and only if the graph has exactly 0 or 2 vertices with odd degree. An **Eulerian circuit** visits every edge and returns to the starting vertex; it requires all vertices to have even degree.

Applications: DNA sequence assembly (de Bruijn graphs), circuit board routing, garbage truck route optimization (Chinese Postman Problem).

> **Key Takeaway:** Floyd-Warshall, network flow, and Eulerian paths are specialized graph algorithms that appear less frequently in day-to-day backend work but are essential for system design (network routing, capacity planning, matching problems) and are common in technical interviews.

---

### String Algorithms

#### KMP (Knuth-Morris-Pratt)

KMP finds all occurrences of a pattern in a text in **O(n + m)** time. The key insight is the **failure function** (also called partial match table), which tells you how far to skip when a mismatch occurs, avoiding redundant comparisons.

```python
def kmp_search(text, pattern):
    """
    Find all occurrences of pattern in text using KMP algorithm.
    Time: O(n + m) where n = len(text), m = len(pattern)
    """
    def build_failure_function(pattern):
        m = len(pattern)
        failure = [0] * m
        length = 0
        i = 1
        while i < m:
            if pattern[i] == pattern[length]:
                length += 1
                failure[i] = length
                i += 1
            elif length > 0:
                length = failure[length - 1]
            else:
                failure[i] = 0
                i += 1
        return failure

    n, m = len(text), len(pattern)
    if m == 0:
        return []

    failure = build_failure_function(pattern)
    matches = []
    j = 0  # Pattern index

    for i in range(n):
        while j > 0 and text[i] != pattern[j]:
            j = failure[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == m:
            matches.append(i - m + 1)
            j = failure[j - 1]

    return matches

text = "ABABDABACDABABCABAB"
print(kmp_search(text, "ABABCABAB"))  # [10]
print(kmp_search(text, "ABAB"))       # [0, 10, 15]
```

**How to read this output:** The returned lists are the 0-based start indices of every match. The second search is the interesting one: `"ABAB"` matches at index 15, then *again* at... no — indices 0, 10, 15 are non-overlapping here, but note KMP deliberately resets `j = failure[j - 1]` after a hit rather than to 0, so it *can* report overlapping matches (searching `"AA"` in `"AAAA"` returns `[0, 1, 2]`). That single-pass, no-backtracking behavior is the whole point: KMP never re-examines a text character, giving the guaranteed O(n + m) that naive `text.find` in a loop cannot promise on adversarial inputs like `"AAAA...AAB"`.

#### Rabin-Karp

Rabin-Karp uses a **rolling hash** to find pattern matches. It computes a hash for the pattern and then slides a window across the text, updating the hash in O(1) for each position. When hashes match, it verifies with a character-by-character comparison to avoid false positives.

It excels at **multi-pattern matching**: hash all patterns and look for any match in a single pass through the text. Used in plagiarism detection tools and content fingerprinting.

#### Aho-Corasick

Aho-Corasick builds an automaton from multiple patterns that searches for all of them simultaneously in a single pass through the text in **O(n + m + z)** time, where z is the number of matches. It is essentially a trie with failure links (like KMP's failure function, but for a set of patterns).

**Real-world use:** Intrusion detection systems (matching known attack signatures), content filtering, antivirus pattern scanning, log analysis.

#### Suffix Array / Suffix Tree

A **suffix array** is a sorted array of all suffixes of a string. It can be constructed in O(n) time and enables O(m log n) substring search (where m is the query length). A **suffix tree** provides O(m) substring search but uses more memory.

**Real-world use:** Bioinformatics (genome sequence matching), full-text search engines, data compression (BWT-based compression like bzip2).

> **Key Takeaway:** String algorithms power many backend features: search, pattern matching, content filtering, and text analysis. Python's built-in `in` operator and `str.find()` use optimized versions of these algorithms internally, but understanding them helps you choose the right approach for specialized needs like multi-pattern matching or fuzzy search.

---

### Randomized & Streaming Algorithms

Streaming algorithms process data in a **single pass** with **memory far smaller than the data**, accepting randomness or approximation in exchange. They are essential when the input is too large to store or arrives continuously (logs, metrics, clickstreams). (The probabilistic *data structures* — Bloom filter, HyperLogLog, Count-Min Sketch — live in the Data Structures section; here we focus on the algorithmic techniques.)

#### Reservoir Sampling

Reservoir sampling selects **k uniformly random items from a stream of unknown length** in one pass, using only O(k) memory — so every element has an equal probability of being chosen even though you never know the total count in advance. Keep the first k items; for each later item `i` (0-indexed), keep it with probability `k/(i+1)`, evicting a random current member if so.

```python
import random

def reservoir_sample(stream, k):
    """Uniformly sample k items from an iterable of unknown length, one pass."""
    reservoir = []
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)              # fill the reservoir first
        else:
            j = random.randint(0, i)            # 0..i inclusive
            if j < k:
                reservoir[j] = item             # keep with prob k/(i+1)
    return reservoir

# Sample 3 log lines from a (conceptually unbounded) stream:
sample = reservoir_sample(range(1_000_000), k=3)
print(sample)   # e.g. [428193, 12, 750021] — different every run, each item equally likely
```

```text
[428193, 12, 750021]
```

**How to read this output:** You get a uniform random sample without ever knowing the stream length up front and without buffering it — exactly what you need for **log sampling** (keep 1% of requests for tracing), **A/B test bucketing**, and **telemetry** where storing every event is impossible. The non-obvious part for an interview: the `k/(i+1)` probability is precisely what keeps the distribution uniform as the stream grows; a fixed "keep with probability p" would over-represent early items.

#### Misra-Gries / Heavy Hitters

The **heavy hitters** problem asks: which elements occur more than `n/k` times in a stream? You cannot keep an exact count per distinct element (that is unbounded memory), so the **Misra-Gries** algorithm keeps only `k-1` counters. Increment a counter for a tracked item; if a new item appears and all counters are taken, decrement *all* counters and drop any that hit zero. After one pass, the surviving counters are a superset of the true heavy hitters (a second pass can verify exact counts).

```python
def misra_gries(stream, k):
    """Approximate heavy hitters: candidates appearing > n/k times. Uses k-1 counters."""
    counters = {}
    for item in stream:
        if item in counters:
            counters[item] += 1
        elif len(counters) < k - 1:
            counters[item] = 1
        else:
            # all counters in use: decrement every one, drop those reaching 0
            for key in list(counters):
                counters[key] -= 1
                if counters[key] == 0:
                    del counters[key]
    return counters   # candidate set (overestimate-free for true heavy hitters)

traffic = ["A","A","A","B","C","A","A","D","A","B","A"]
print(misra_gries(traffic, k=2))   # {'A': ...} -> "A" is the dominant heavy hitter
```

**Real-world use:** network "top talkers" (which IPs send the most packets), trending-content detection, and finding the hot keys overloading a cache or shard — all with bounded memory regardless of how many distinct items flow through.

#### Monte Carlo vs Las Vegas

Randomized algorithms come in two flavors, and the distinction is a common interview question:

- **Monte Carlo:** runs in **bounded (often deterministic) time** but may give a **wrong answer with small probability**. You trade correctness for speed, and you can drive the error rate arbitrarily low by repeating (e.g., the Miller-Rabin primality test, randomized min-cut, Bloom-filter membership).
- **Las Vegas:** **always returns the correct answer**, but its **running time is random**. Randomized quicksort is the canonical example — its output is always sorted; only *how long it takes* depends on the random pivots (avoiding the O(n²) worst case on adversarial/sorted input that a fixed pivot would hit).

A useful mnemonic: **Monte Carlo gambles on the answer; Las Vegas gambles on the time.** In production, randomization most often appears as the Las Vegas kind — random pivots, randomized hash seeds, jittered retry backoff — used specifically to make worst-case-triggering inputs (whether accidental or adversarial) astronomically unlikely.

> **Key Takeaway:** When data is unbounded or too large to store, switch from "compute the exact answer" to "approximate it in one pass with bounded memory." Reservoir sampling gives uniform samples without knowing the length; Misra-Gries finds heavy hitters in tiny space; and knowing the Monte Carlo / Las Vegas distinction explains *why* the randomization in everyday tools (quicksort pivots, retry jitter, SipHash) is there — to convert worst cases into vanishingly rare cases.

*Last reviewed: 2026-06-08*
