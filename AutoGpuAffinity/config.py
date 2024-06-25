import logging
import os
from configparser import ConfigParser
from dataclasses import dataclass
from enum import Enum

LOG_CONFIG = logging.getLogger("CONFIG")


class Api(Enum):
    LIBLAVA = 1
    D3D9 = 2


@dataclass
class Settings:
    cache_duration: int
    benchmark_duration: int
    custom_cpus: list[int]
    api: Api
    sync_driver_affinity: bool
    skip_confirmation: bool


@dataclass
class MSIAfterburner:
    profile: int
    location: str


@dataclass
class Xperf:
    enabled: bool
    location: str
    save_etls: bool


@dataclass
class Liblava:
    fullscreen: bool
    x_resolution: int
    y_resolution: int
    fps_cap: int
    triple_buffering: bool


class Config:
    def __init__(self, config_path: str):
        if not os.path.exists(config_path):
            error_msg = f"config file not found at path: {config_path}"
            LOG_CONFIG.error(error_msg)
            raise FileNotFoundError(error_msg)

        config = ConfigParser(delimiters="=")
        config.read(config_path)

        apis: dict[int, Api] = {
            1: Api.LIBLAVA,
            2: Api.D3D9,
        }

        self.settings = Settings(
            cache_duration=config.getint("settings", "cache_duration"),
            benchmark_duration=config.getint("settings", "benchmark_duration"),
            custom_cpus=Config.str_to_int_array(config.get("settings", "custom_cpus")),
            api=apis[config.getint("settings", "api")],
            sync_driver_affinity=config.getboolean("settings", "sync_driver_affinity"),
            skip_confirmation=config.getboolean("settings", "skip_confirmation"),
        )

        self.msi_afterburner = MSIAfterburner(
            profile=config.getint("MSI Afterburner", "profile"),
            location=config.get("MSI Afterburner", "location"),
        )

        self.xperf = Xperf(
            config.getboolean("xperf", "enabled"),
            config.get("xperf", "location"),
            config.getboolean("xperf", "save_etls"),
        )

        self.liblava = Liblava(
            config.getboolean("liblava", "fullscreen"),
            config.getint("liblava", "x_resolution"),
            config.getint("liblava", "y_resolution"),
            config.getint("liblava", "fps_cap"),
            config.getboolean("liblava", "triple_buffering"),
        )

    def validate_config(self):
        errors = 0

        if self.settings.cache_duration < 0 or self.settings.benchmark_duration <= 0:
            LOG_CONFIG.error("invalid durations specified")
            errors += 1

        if self.xperf.enabled and not os.path.exists(self.xperf.location):
            LOG_CONFIG.error("invalid xperf path specified")
            errors += 1

        if self.msi_afterburner.profile > 0 and not os.path.exists(
            self.msi_afterburner.location,
        ):
            LOG_CONFIG.error("invalid MSI Afterburner path specified")
            errors += 1

        if self.settings.api not in Api:
            LOG_CONFIG.error("invalid api specified")
            errors += 1

        return 1 if errors else 0

    @staticmethod
    def str_to_int_array(str_array: str) -> list[int]:
        # return if empty
        if str_array == "[]":
            return []

        # convert to list[str]
        str_array_without_brackets = str_array[1:-1]
        split_array = [x.strip() for x in str_array_without_brackets.split(",")]

        parsed_list: list[int] = []

        for item in split_array:
            if ".." in item:
                lower, upper = item.split("..")
                parsed_list.extend(range(int(lower), int(upper) + 1))
            else:
                parsed_list.append(int(item))

        return parsed_list
