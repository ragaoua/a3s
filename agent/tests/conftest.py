from pydantic_settings import SettingsConfigDict

import src.config as config


class TestConfig(config.Config):
    model_config = SettingsConfigDict(env_file=None)


config.Config = TestConfig
