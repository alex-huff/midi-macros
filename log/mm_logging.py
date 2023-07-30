import sys
from threading import local
from contextlib import contextmanager

context = local()


@contextmanager
def loggingContext(profile=None, subprofile=None):
    oldProfile = getProfile()
    oldSubprofile = getSubprofile()
    setContext(
        profile if profile else oldProfile, subprofile if subprofile else oldSubprofile
    )
    try:
        yield None
    finally:
        setContext(oldProfile, oldSubprofile)


def setContext(profile=None, subprofile=None):
    context.profile = profile
    context.subprofile = subprofile


def getProfile():
    return getattr(context, "profile", None)


def getSubprofile():
    return getattr(context, "subprofile", None)


def exceptionStr(exception):
    return getattr(exception, "message", repr(exception))


def logInfo(message):
    log(message, "INFO", sys.stdout)


def logError(message):
    log(message, "ERROR", sys.stderr)


def log(message, level, file):
    profile = getProfile()
    subprofile = getSubprofile()
    if profile:
        if subprofile:
            profileSpecifier = f"[{profile}][{subprofile}]: "
        else:
            profileSpecifier = f"[{profile}]: "
    else:
        profileSpecifier = ""
    print(f"{profileSpecifier}{level}: {message}", file=file)
