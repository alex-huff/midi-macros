from threading import Lock, RLock
from contextlib import contextmanager

lockLock = Lock()
locks = {}

@contextmanager
def lockContext(lockNames):
    for lockName in lockNames:
        getLock(lockName).acquire()
    try:
        yield None
    finally:
        for lockName in lockNames:
            getLock(lockName).release()


def getLock(lockName):
    with lockLock:
        lock = locks.get(lockName)
        if not lock:
            lock = RLock()
            locks[lockName] = lock
        return lock

def clearLocks():
    with lockLock:
        locks.clear()
