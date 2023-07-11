class Callback:
    def __init__(self, profileName, callbackType, script, message):
        self.profileName = profileName
        self.callbackType = callbackType
        self.script = script
        self.message = message

    def getProfileName(self):
        return self.profileName

    def getCallbackType(self):
        return self.callbackType

    def getScript(self):
        return self.script

    def getMessage(self):
        return self.message
