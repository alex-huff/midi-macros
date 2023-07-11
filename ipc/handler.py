from log.mm_logging import logInfo

TOGGLE = "toggle"
ENABLE = "enable"
DISABLE = "disable"
RELOAD = "reload"
PROFILE = "profile"
GET_LOADED_PROFILES = "get-loaded-profiles"
VIRTUAL_SUSTAIN = "virtual-sustain"


def failResponse(string):
    return (False, string)


def successResponse(string):
    return (True, string)


def handleMessage(message, midiMacros):
    if len(message) == 0:
        return failResponse("empty message")
    messageType = message[0]
    if messageType == RELOAD:
        return handleReloadMessage(message, 1, midiMacros)
    elif messageType == PROFILE:
        return handleProfileMessage(message, 1, midiMacros)
    elif messageType == GET_LOADED_PROFILES:
        return handleGetLoadedProfilesMessage(message, 1, midiMacros)
    return failResponse("invalid message type")


def handleReloadMessage(message, position, midiMacros):
    if len(message) > position:
        return failResponse("reload message takes no arguments")
    if not midiMacros.reload():
        return failResponse("failed to reload config. check logs for details")
    return successResponse("successfully reloaded all profiles")


def handleGetLoadedProfilesMessage(message, position, midiMacros):
    if len(message) > position:
        return failResponse("get-loaded-profiles message takes no arguments")
    return successResponse("\n".join(midiMacros.getLoadedProfiles()))


def handleProfileMessage(message, position, midiMacros):
    if len(message) < position + 2:
        return failResponse(
            "not enough arguments, profile name and message type required"
        )
    profileName = message[position]
    messageType = message[position + 1]
    midiListener = midiMacros.getProfile(profileName)
    if not midiListener:
        return failResponse("invalid profile")
    position += 2
    if messageType in (TOGGLE, ENABLE, DISABLE):
        if len(message) > position:
            return failResponse(f"profile {messageType} takes no arguments")
    if messageType == TOGGLE:
        enabled = midiListener.toggleEnabled()
        return successResponse(f'profile is now {"enabled" if enabled else "disabled"}')
    elif messageType == ENABLE:
        midiListener.setEnabled(True)
        return successResponse("profile is now enabled")
    elif messageType == DISABLE:
        midiListener.setEnabled(False)
        return successResponse("profile is now disabled")
    elif messageType == VIRTUAL_SUSTAIN:
        return handleVirtualSustainMessage(message, position, midiListener)
    return failResponse("invalid message type after profile")


def handleVirtualSustainMessage(message, position, midiListener):
    if len(message) != position + 1:
        return failResponse(
            "profile virtual-sustain message takes exactly one argument"
        )
    action = message[position]
    if action == TOGGLE:
        enabled = midiListener.toggleVirtualPedalDown()
        return successResponse(
            f'virtual-sustain is now {"enabled" if enabled else "disabled"}'
        )
    elif action == ENABLE:
        midiListener.setVirtualPedalDown(True)
        return successResponse("virtual-sustain is now enabled")
    elif action == DISABLE:
        midiListener.setVirtualPedalDown(False)
        return successResponse("virtual-sustain is now disabled")
    return failResponse("invalid virtual-sustain action")
