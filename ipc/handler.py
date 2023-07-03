from log.mm_logging import logInfo

def handleMessage(message, midiMacros):
    if (len(message) == 0):
        return (False, 'empty message')
    match (message[0]):
        case 'reload':
            return handleReloadMessage(message, 1, midiMacros)
        case 'get-loaded-profiles':
            return handleGetLoadedProfilesMessage(message, 1, midiMacros)
    return (False, 'unknown message')

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
