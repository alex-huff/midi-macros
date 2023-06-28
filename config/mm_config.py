import os


class ConfigError(Exception):
    def __init__(self, message):
        self.message = message

    def getMessage(self):
        return self.message


def getDefaultConfig():
    return {
        'enabled': True,
        'midi-input': None,
        'macro-file': None
    }


def getMacroPath(path, macroDirPath):
    path = os.path.expanduser(path)
    if (not os.path.isabs(path)):
        path = os.path.join(macroDirPath, path)
    if (os.path.exists(path)):
        if (not os.path.isdir(path)):
            return path
        raise ConfigError(f'macro file: {path} is a directory')
    raise ConfigError(f'macro file: {path} does not exist')


def loadConfigFromTOMLDictionary(toml, macroDirPath):
    config = getDefaultConfig()
    for key, value in toml.items():
        if (key not in config):
            raise ConfigError(f'key: "{key}" is not a valid setting')
        if (key == 'macro-file'):
            value = getMacroPath(value, macroDirPath)
        config[key] = value
    return config
