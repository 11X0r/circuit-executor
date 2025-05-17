import os
import tomli
from pathlib import Path

# Default configuration - optimized for running in containers
default_config = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000
    },
    "nats": {
        # Default to container service name but allow override
        "url": os.environ.get("NATS_URL", "nats:4222"),
        "subject": "tasks",
        "max_reconnect_attempts": 5,
        "reconnect_time_wait": 2
    },
    "redis": {
        # Default to container service name but allow override
        "url": os.environ.get("REDIS_URL", "redis://redis:6379"),
        "db": 0
    },
    "quantum": {
        "shots": 1024
    },
    "worker": {
        "max_concurrent_tasks": os.cpu_count() or 4
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}

# Try to load config file if it exists
config_path = Path("config/config.toml")
config = default_config.copy()

if config_path.exists():
    try:
        with open(config_path, "rb") as f:
            file_config = tomli.load(f)
            
        # Merge file config with defaults
        for section, values in file_config.items():
            if section in config:
                config[section].update(values)
            else:
                config[section] = values
    except Exception as e:
        print(f"Error loading config file: {e}")
