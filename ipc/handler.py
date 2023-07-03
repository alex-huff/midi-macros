from log.mm_logging import logInfo


def handleMessage(message, midiMacros):
    if (len(message) == 0):
        return (False, 'empty message')
    messageType = message[0]
    match (messageType):
        case 'reload':
            return handleReloadMessage(message, 1, midiMacros)
        case 'get-loaded-profiles':
            return handleGetLoadedProfilesMessage(message, 1, midiMacros)
        case 'profile':
            return handleProfileMessage(message, 1, midiMacros)
    return (False, 'invalid message type')


def handleReloadMessage(message, position, midiMacros):
    if (len(message) > position):
        return (False, 'reload message takes no arguments')
    if (not midiMacros.reloadConfig()):
        return (False, 'failed to reload configuration, check logs for details')
    logInfo('stopping listeners')
    midiMacros.stopListeners()
    logInfo('restarting listeners')
    midiMacros.createAndRunListeners()
    return (True, 'successfully reloaded all profiles')


def handleGetLoadedProfilesMessage(message, position, midiMacros):
    if (len(message) > position):
        return (False, 'get-loaded-profiles message takes no arguments')
    return (True, '\n'.join(midiMacros.getLoadedProfiles()))


def handleProfileMessage(message, position, midiMacros):
    if (len(message) < position + 2):
        return (False, 'not enough arguments, profile name and message type required')
    profileName = message[position]
    messageType = message[position + 1]
    midiListener = midiMacros.getProfile(profileName)
    if (not midiListener):
        return (False, 'invalid profile')
    position += 2
    match (messageType):
        case 'toggle':
            enabled = midiListener.toggleEnabled()
            return (True, f'profile is now {"enabled" if enabled else "disabled"}')
        case 'enable':
            midiListener.setEnabled(True)
            return (True, 'profile is now enabled')
        case 'disable':
            midiListener.setEnabled(False)
            return (True, 'profile is now disabled')
        case 'virtual-sustain':
            return (False, 'not yet implemented')
    return (False, 'invalid message type after profile')
