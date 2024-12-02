import queue


qu = queue.Queue()

qu.put([1, 2, 3])
qu.put([4, 5, 6])


print(qu.get_nowait())
print(qu.get_nowait())

try:
    qu.get_nowait()
except queue.Empty:
    ...