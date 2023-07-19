import tomllib


class ConfigException(Exception):
    def __init__(self, message, profile=None, subprofile=None):
        self.message = message
        self.profile = profile
        self.subprofile = subprofile


# setting types
GLOBAL = "global"
PROFILE = "profile"
SUBPROFILE = "subprofile"

# shared settings
ENABLED = "enabled"

# global settings
SOCKET_PATH = "socket-path"

# profile settings
MIDI_INPUT = "midi-input"
GLOBAL_MACROS = "global-macros"
ENABLE_TRIGGER = "enable-trigger"
CYCLE_SUBPROFILES_TRIGGER = "cycle-subprofiles-trigger"
ENABLE_CALLBACK = "enable-callback"
VIRTUAL_SUSTAIN_CALLBACK = "virtual-sustain-callback"
SUBPROFILE_CALLBACK = "subprofile-callback"
DEBOUNCE_CALLBACKS = "debounce-callbacks"

# subprofile settings
MACROS = "macros"

CALLBACK_TYPES = set((ENABLE_CALLBACK, VIRTUAL_SUSTAIN_CALLBACK, SUBPROFILE_CALLBACK))
TRIGGER_TYPES = set((ENABLE_TRIGGER, CYCLE_SUBPROFILES_TRIGGER))

PROFILES = "profiles"
SUBPROFILES = "subprofiles"

GLOBAL_SETTINGS = {SOCKET_PATH: str}
PROFILE_SETTINGS = {
    ENABLED: bool,
    MIDI_INPUT: str,
    GLOBAL_MACROS: str,
    ENABLE_TRIGGER: str,
    CYCLE_SUBPROFILES_TRIGGER: str,
    ENABLE_CALLBACK: str,
    VIRTUAL_SUSTAIN_CALLBACK: str,
    SUBPROFILE_CALLBACK: str,
    DEBOUNCE_CALLBACKS: bool,
}
SUBPROFILE_SETTINGS = {ENABLED: bool, MACROS: str}
SETTINGS = {
    GLOBAL: GLOBAL_SETTINGS,
    PROFILE: PROFILE_SETTINGS,
    SUBPROFILE: SUBPROFILE_SETTINGS,
}

REQUIRED_GLOBAL_SETTINGS = set()
REQUIRED_PROFILE_SETTINGS = set((ENABLED, MIDI_INPUT, DEBOUNCE_CALLBACKS))
REQUIRED_SUBPROFILE_SETTINGS = set((ENABLED, MACROS))
REQUIRED_SETTINGS = {
    GLOBAL: REQUIRED_GLOBAL_SETTINGS,
    PROFILE: REQUIRED_PROFILE_SETTINGS,
    SUBPROFILE: REQUIRED_SUBPROFILE_SETTINGS,
}


def getDefaultGlobalConfig():
    return {}


def getDefaultProfileConfig():
    return {ENABLED: True, DEBOUNCE_CALLBACKS: True}


def getDefaultSubprofileConfig():
    return {ENABLED: True}


def verifySettingType(key, value, configType, profile=None, subprofile=None):
    settings = SETTINGS[configType]
    expectedType = settings[key]
    actualType = type(value)
    if expectedType != actualType:
        raise ConfigException(
            f"setting: {key}, should be of type: {expectedType.__name__}",
            profile,
            subprofile,
        )


def verifyRequiredSettingsPresent(settings, configType, profile=None, subprofile=None):
    requiredSettings = REQUIRED_SETTINGS[configType]
    for setting in requiredSettings:
        if setting not in settings:
            raise ConfigException(
                f"required setting: {setting}, is not present", profile, subprofile
            )


def loadConfig(configFilePath):
    config = getDefaultGlobalConfig()
    profiles = {}
    with open(configFilePath, "rb") as configFile:
        data = tomllib.load(configFile)
    for key, value in data.items():
        if isinstance(value, dict):
            profileConfig = loadProfileConfig(key, value)
            if profileConfig[ENABLED]:
                profiles[key] = profileConfig
            continue
        if key not in GLOBAL_SETTINGS:
            raise ConfigException(f"setting: {key}, is not a valid setting")
        verifySettingType(key, value, GLOBAL)
        config[key] = value
    config[PROFILES] = profiles
    verifyRequiredSettingsPresent(config, GLOBAL)
    return config


def loadProfileConfig(profile, tomlTable):
    config = getDefaultProfileConfig()
    subprofiles = {}
    for key, value in tomlTable.items():
        if isinstance(value, dict):
            subprofileConfig = loadSubprofileConfig(profile, key, value)
            if subprofileConfig[ENABLED]:
                subprofiles[key] = subprofileConfig
            continue
        if key not in PROFILE_SETTINGS:
            raise ConfigException(f"setting: {key}, is not a valid setting", profile)
        verifySettingType(key, value, PROFILE, profile)
        config[key] = value
    config[SUBPROFILES] = subprofiles
    verifyRequiredSettingsPresent(config, PROFILE, profile)
    return config


def loadSubprofileConfig(profile, subprofile, tomlTable):
    config = getDefaultSubprofileConfig()
    for key, value in tomlTable.items():
        if key not in SUBPROFILE_SETTINGS:
            raise ConfigException(
                f"setting: {key}, is not a valid setting", profile, subprofile
            )
        verifySettingType(key, value, SUBPROFILE, profile, subprofile)
        config[key] = value
    verifyRequiredSettingsPresent(config, SUBPROFILE, profile, subprofile)
    return config
