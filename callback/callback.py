class Callback:
    def __init__(self, profile, callbackType, script, message):
        self.profile = profile
        self.callbackType = callbackType
        self.script = script
        self.message = message

    def getProfile(self):
        return self.profile

    def getCallbackType(self):
        return self.callbackType

    def getScript(self):
        return self.script

    def getMessage(self):
        return self.message
