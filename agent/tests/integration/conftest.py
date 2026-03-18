from pydantic_settings import SettingsConfigDict

import src.config as config


# We want tests to ignore env_file loading
class TestConfig(config.Config):
    model_config = SettingsConfigDict(env_file=None)


config.Config = TestConfig
