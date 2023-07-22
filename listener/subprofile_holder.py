from config.mm_config import MACROS


class SubprofileHolder:
    def __init__(self, subprofiles):
        self.subprofiles = subprofiles
        self.names = tuple(self.subprofiles.keys())
        self.numSubprofiles = len(self.names)
        assert self.numSubprofiles
        self.current = 0

    def cycle(self):
        if self.numSubprofiles == 1:
            return False
        if self.current == self.numSubprofiles - 1:
            self.current = 0
        else:
            self.current += 1
        return True

    def getCurrent(self):
        return self.names[self.current]

    def getCurrentMacroTree(self):
        return self.subprofiles[self.getCurrent()][MACROS]

    def setCurrent(self, subprofile):
        index = self.names.index(subprofile)
        if self.current == index:
            return False
        self.current = index
        return True

    def getNames(self):
        return self.names

    def getInfo(self):
        return {"current": self.getCurrent(), "all": self.names}

    def wait(self):
        for subprofileConfig in self.subprofiles.values():
            subprofileConfig[MACROS].wait()
