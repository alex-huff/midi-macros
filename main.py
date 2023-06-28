import os
import sys
import threading
import tomllib
from appdirs import user_config_dir
from config.mm_config import loadConfigFromTOMLDictionary, ConfigError
from listener.midi_listener import MidiListener

configDirPath = user_config_dir('midi-macros')
macroDirPath = os.path.join(configDirPath, 'macros')

def verifyDirectoryExists(path, name):
    if (not os.path.exists(path)):
        print(f'INFO: {name} directory {path} does not exist, creating it now')
        os.makedirs(path)
    elif (not os.path.isdir(path)):
        print(
            f'ERROR: {name} directory {path} already exists as a file', file=sys.stderr)
        sys.exit(-1)

verifyDirectoryExists(configDirPath, 'config')
verifyDirectoryExists(macroDirPath, 'macro')
configFilePath = os.path.join(configDirPath, 'midi-macros.toml')

if (not os.path.exists(configFilePath)):
    print(f'Config file {configFilePath} does not exist, creating it now')
    open(configFilePath, 'a').close()

listeners = {}

with open(configFilePath, 'rb') as configFile:
    data = tomllib.load(configFile)

for key, value in data.items():
    if (not isinstance(value, dict)):
        print(
            f'Top level non-table item: "{key}" found. All configuration must be done in tables named after the corresponding profile. See: https://toml.io/en/v1.0.0#table', file=sys.stderr)
        sys.exit(-1)
    try:
        config = loadConfigFromTOMLDictionary(value, macroDirPath)
    except ConfigError as ce:
        print(f'ERROR: {ce.getMessage()}', file=sys.stderr)
        sys.exit(-1)
    if (not config['enabled']):
        continue
    listeners[key] = MidiListener(config, key)

for listener in listeners.values():
    threading.Thread(target=listener.run).run()
