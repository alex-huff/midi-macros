import sys


def exceptionStr(exception):
    return getattr(exception, "message", repr(exception))


def logInfo(message, profile=None, subprofile=None):
    log(message, "INFO", sys.stdout, profile, subprofile)


def logError(message, profile=None, subprofile=None):
    log(message, "ERROR", sys.stderr, profile, subprofile)


def log(message, level, file, profile=None, subprofile=None):
    if profile:
        if subprofile:
            profileSpecifier = f"[{profile}][{subprofile}]"
        else:
            profileSpecifier = f"[{profile}]"
    else:
        profileSpecifier = ""
    print(f"{profileSpecifier}: {level}: {message}", file=file)
