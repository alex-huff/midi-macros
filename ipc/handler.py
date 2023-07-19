TOGGLE = "toggle"
ENABLE = "enable"
DISABLE = "disable"
RELOAD = "reload"
PROFILE = "profile"
GET_LOADED_PROFILES = "get-loaded-profiles"
GET_LOADED_SUBPROFILES = "get-loaded-subprofiles"
CYCLE_SUBPROFILES = "cycle-subprofiles"
SET_SUBPROFILE = "set-subprofile"
VIRTUAL_SUSTAIN = "virtual-sustain"


def failResponse(string):
    return (False, string)


def successResponse(string):
    return (True, string)


def handleMessage(message, midiMacros):
    if len(message) == 0:
        return failResponse("empty message")
    messageType = message[0]
    if messageType in (RELOAD, GET_LOADED_PROFILES):
        if len(message) > 1:
            return failResponse(f"{messageType} takes no arguments")
    if messageType == RELOAD:
        if not midiMacros.reload():
            return failResponse("failed to reload config")
        return successResponse("successfully reloaded all profiles")
    elif messageType == PROFILE:
        return handleProfileMessage(message, 1, midiMacros)
    elif messageType == GET_LOADED_PROFILES:
        return successResponse("\n".join(midiMacros.getLoadedProfiles()))
    return failResponse(f"invalid message type: {messageType}")


def handleProfileMessage(message, position, midiMacros):
    if len(message) < position + 2:
        return failResponse(
            "not enough arguments, profile name and message type required"
        )
    profile = message[position]
    messageType = message[position + 1]
    midiListener = midiMacros.getProfile(profile)
    if not midiListener:
        return failResponse(f"invalid profile: {profile}")
    position += 2
    if messageType in (
        TOGGLE,
        ENABLE,
        DISABLE,
        GET_LOADED_SUBPROFILES,
        CYCLE_SUBPROFILES,
    ):
        if len(message) > position:
            return failResponse(f"{messageType} takes no arguments")
    if messageType == TOGGLE:
        enabled = midiListener.toggleEnabled()
        return successResponse(
            f'profile: {profile} is now {"enabled" if enabled else "disabled"}'
        )
    elif messageType == ENABLE:
        midiListener.setEnabled(True)
        return successResponse(f"profile: {profile} is now enabled")
    elif messageType == DISABLE:
        midiListener.setEnabled(False)
        return successResponse(f"profile: {profile} is now disabled")
    elif messageType == VIRTUAL_SUSTAIN:
        return handleVirtualSustainMessage(message, position, midiListener)
    elif messageType == GET_LOADED_SUBPROFILES:
        return successResponse("\n".join(midiListener.getSubprofiles()))
    elif messageType == CYCLE_SUBPROFILES:
        newSubprofile = midiListener.cycleSubprofiles()
        if not newSubprofile:
            return failResponse("no loaded subprofiles to cycle through")
        return successResponse(f"active subprofile is now: {newSubprofile}")
    elif messageType == SET_SUBPROFILE:
        return handleSetSubprofile(message, position, midiListener)
    return failResponse(f"invalid message type: {messageType}")


def handleVirtualSustainMessage(message, position, midiListener):
    if len(message) != position + 1:
        return failResponse("virtual-sustain message takes exactly one argument")
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


def handleSetSubprofile(message, position, midiListener):
    if len(message) != position + 1:
        return failResponse("set-subprofile message takes exactly one argument")
    subprofile = message[position]
    try:
        newSubprofile = midiListener.setSubprofile(subprofile)
    except ValueError:
        return failResponse(f"invalid subprofile: {subprofile}")
    if not newSubprofile:
        return failResponse("no loaded subprofiles")
    return successResponse(f"subprofile is now: {newSubprofile}")
