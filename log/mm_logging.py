import sys


def exceptionStr(exception):
    return getattr(exception, "message", repr(exception))


def logInfo(message, profile=None):
    log(message, "INFO", sys.stdout, profile)


def logError(message, profile=None):
    log(message, "ERROR", sys.stderr, profile)


def log(message, level, file, profile=None):
    profileSpecifier = f"[{profile}]: " if profile else ""
    print(f"{profileSpecifier}{level}: {message}", file=file)
