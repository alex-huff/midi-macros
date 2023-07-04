import tomllib


class ConfigException(Exception):
    def __init__(self, message, profile=None):
        self.message = message
        self.profile = profile


SOCKET_PATH = "socket-path"

ENABLED = "enabled"
MIDI_INPUT = "midi-input"
MACRO_FILE = "macro-file"
TOGGLE_TRIGGER = "toggle-trigger"
TOGGLE_CALLBACK = "toggle-callback"
VIRTUAL_SUSTAIN_CALLBACK = "virtual-sustain-callback"

PROFILES = "profiles"

SETTINGS = {SOCKET_PATH: str}
PROFILE_SETTINGS = {
    ENABLED: bool,
    MIDI_INPUT: str,
    MACRO_FILE: str,
    TOGGLE_TRIGGER: str,
    TOGGLE_CALLBACK: str,
    VIRTUAL_SUSTAIN_CALLBACK: str,
}
REQUIRED_SETTINGS = set()
REQUIRED_PROFILE_SETTINGS = set((MIDI_INPUT, MACRO_FILE))


def getDefaultConfig():
    return {}


def getDefaultProfileConfig():
    return {ENABLED: True}


def verifySettingType(key, value, profile=None):
    expectedType = PROFILE_SETTINGS[key] if profile else SETTINGS[key]
    actualType = type(value)
    if expectedType != actualType:
        raise ConfigException(
            f"setting: {key}, should be of type: {expectedType.__name__}", profile
        )


def verifyRequiredSettingsPresent(requiredSettings, settings, profile=None):
    for setting in requiredSettings:
        if setting not in settings:
            raise ConfigException(
                f"required setting: {setting}, is not present", profile
            )


def loadProfileConfig(profileName, tomlTable):
    config = getDefaultProfileConfig()
    for key, value in tomlTable.items():
        if key not in PROFILE_SETTINGS:
            raise ConfigException(
                f"setting: {key}, is not a valid setting", profileName
            )
        verifySettingType(key, value, profileName)
        config[key] = value
    verifyRequiredSettingsPresent(REQUIRED_PROFILE_SETTINGS, config, profileName)
    return config


def loadConfig(configFilePath):
    config = getDefaultConfig()
    profiles = {}
    with open(configFilePath, "rb") as configFile:
        data = tomllib.load(configFile)
    for key, value in data.items():
        if isinstance(value, dict):
            profileConfig = loadProfileConfig(key, value)
            if profileConfig[ENABLED]:
                profiles[key] = profileConfig
            continue
        if key not in SETTINGS:
            raise ConfigException(f"setting: {key}, is not a valid setting")
        verifySettingType(key, value)
        config[key] = value
    config[PROFILES] = profiles
    verifyRequiredSettingsPresent(REQUIRED_SETTINGS, config)
    return config
