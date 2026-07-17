import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, TypeVar, Type, Callable

T = TypeVar('T')

class Config:
    # Typed properties
    IMAGE_DIR: Path
    OCR_THRESHOLD: float
    HOURS_TO_UNLOCK_DAILY_MISSIONS: int

    GAME_PACKAGE: str
    GAME_START_HEART: int
    GAME_START_LEVEL: int
    GAME_START_DRILL: int
    GAME_START_HAMMER: int
    GAME_START_MAGNET: int
    GAME_START_COIN: int
    GAME_START_PLAY_SPEED: float

    RECOVERY_GATE_TIMEOUT: float
    RECOVERY_COLD_PLAYSPEED: float
    RECOVERY_LOAD_WAIT_SEC: float
    RECOVERY_APP_UP_TIMEOUT: float

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self._data: Dict[str, Any] = {}
        
        self._load_env()
        self._load_json()
        
        # Hardcoded paths and constants
        self.IMAGE_DIR = self.base_dir / "pixon" / "pages" / "images"
        self.OCR_THRESHOLD = 0.7
        self.HOURS_TO_UNLOCK_DAILY_MISSIONS = 72

        # Configuration variables with defaults
        self.GAME_PACKAGE = self.env("GAME_PACKAGE", "com.woodpuzzle.pin3d", str)
        self.GAME_START_HEART = self.env("GAME_START_HEART", 5, int)
        self.GAME_START_LEVEL = self.env("GAME_START_LEVEL", 3, int)
        self.GAME_START_DRILL = self.env("GAME_START_DRILL", 20, int)
        self.GAME_START_HAMMER = self.env("GAME_START_HAMMER", 20, int)
        self.GAME_START_MAGNET = self.env("GAME_START_MAGNET", 20, int)
        self.GAME_START_COIN = self.env("GAME_START_COIN", 5000, int)
        self.GAME_START_PLAY_SPEED = self.env("GAME_START_PLAY_SPEED", 6.0, float)

        # Recovery settings
        self.RECOVERY_GATE_TIMEOUT = self.env("RECOVERY_GATE_TIMEOUT", 5.0, float)
        self.RECOVERY_COLD_PLAYSPEED = self.env("RECOVERY_COLD_PLAYSPEED", 6.0, float)
        self.RECOVERY_LOAD_WAIT_SEC = self.env("RECOVERY_LOAD_WAIT_SEC", 30.0, float)
        self.RECOVERY_APP_UP_TIMEOUT = self.env("RECOVERY_APP_UP_TIMEOUT", 30.0, float)

        self._validate()

    def _validate(self) -> None:
        """Validate critical configuration invariants at startup."""
        if not self.GAME_PACKAGE:
            raise ValueError("Config validation failed: GAME_PACKAGE cannot be empty.")
        if not (0.0 < self.OCR_THRESHOLD <= 1.0):
            raise ValueError(f"Config validation failed: OCR_THRESHOLD {self.OCR_THRESHOLD} must be in (0, 1].")
        if self.GAME_START_HEART < 0:
            raise ValueError(f"Config validation failed: GAME_START_HEART {self.GAME_START_HEART} must be >= 0.")
        if self.GAME_START_LEVEL <= 0:
            raise ValueError(f"Config validation failed: GAME_START_LEVEL {self.GAME_START_LEVEL} must be > 0.")
        if self.GAME_START_PLAY_SPEED <= 0:
            raise ValueError(f"Config validation failed: GAME_START_PLAY_SPEED {self.GAME_START_PLAY_SPEED} must be > 0.")
        if self.RECOVERY_GATE_TIMEOUT <= 0:
            raise ValueError("Config validation failed: RECOVERY_GATE_TIMEOUT must be > 0.")

    def _load_env(self) -> None:
        """Simple .env parser"""
        env_file = self.base_dir / ".env"
        if not env_file.exists():
            return
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        self._data[k.strip()] = v.strip().strip("'\"")
        except Exception as e:
            logging.warning(f"Failed to load .env: {e}")

    def _load_json(self) -> None:
        config_file = self.base_dir / "config.json"
        if not config_file.exists():
            return
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                if isinstance(json_data, dict):
                    self._data.update(json_data)
        except Exception as e:
            logging.warning(f"Failed to load config.json: {e}")

    def env(self, key: str, default: T, cast_type: Callable[[Any], T]) -> T:
        """Fetch env variable from os.environ, json, or .env and safely cast."""
        val: Any
        if key in os.environ:
            val = os.environ[key]
        else:
            val = self._data.get(key, default)
            
        if val is default:
            return default
            
        try:
            return cast_type(val)
        except (ValueError, TypeError):
            logging.warning(f"Failed to cast {key}='{val}' to {cast_type.__name__}, using default {default}")
            return default

# Create singleton instance
config = Config()

# Export variables for backwards compatibility
IMAGE_DIR = config.IMAGE_DIR
OCR_THRESHOLD = config.OCR_THRESHOLD
GAME_PACKAGE = config.GAME_PACKAGE
GAME_START_HEART = config.GAME_START_HEART
GAME_START_LEVEL = config.GAME_START_LEVEL
GAME_START_DRILL = config.GAME_START_DRILL
GAME_START_HAMMER = config.GAME_START_HAMMER
GAME_START_MAGNET = config.GAME_START_MAGNET
GAME_START_COIN = config.GAME_START_COIN
GAME_START_PLAY_SPEED = config.GAME_START_PLAY_SPEED
HOURS_TO_UNLOCK_DAILY_MISSIONS = config.HOURS_TO_UNLOCK_DAILY_MISSIONS
RECOVERY_GATE_TIMEOUT = config.RECOVERY_GATE_TIMEOUT
RECOVERY_COLD_PLAYSPEED = config.RECOVERY_COLD_PLAYSPEED
RECOVERY_LOAD_WAIT_SEC = config.RECOVERY_LOAD_WAIT_SEC
RECOVERY_APP_UP_TIMEOUT = config.RECOVERY_APP_UP_TIMEOUT
