def nanoSecondsToSeconds(elapsedTime):
    return elapsedTime / 10**9


def nanoSecondsToMilliseconds(elapsedTime):
    return elapsedTime / 10**6


SECONDS = nanoSecondsToSeconds
sec = SECONDS
MILLISECONDS = nanoSecondsToMilliseconds
ms = MILLISECONDS
