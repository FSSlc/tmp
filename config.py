import os
import threading

from dotenv import dotenv_values
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver


class Settings(BaseModel):
    app_name: str = Field(description="应用名称")
    admin_email: str = Field(description="管理员邮箱")
    items_per_user: int = Field(description="每个用户配额")


def load_settings(env_path=".env") -> Settings:
    envs = dotenv_values(env_path)
    config = {
        "app_name": envs.get("APP_NAME"),
        "admin_email": envs.get("ADMIN_EMAIL"),
        "items_per_user": int(envs.get("ITEMS_PER_USER")),
    }
    return Settings(**config)


class EnvHandler(FileSystemEventHandler):
    def __init__(self, env_path, on_reload):
        self.env_path = env_path
        self.on_reload = on_reload
        self.load_config()

    def load_config(self):
        settings = load_settings(self.env_path)
        self.on_reload(settings)
        print(f"Config reloaded: {settings}")

    def on_modified(self, event):
        if event.src_path == os.path.abspath(self.env_path):
            print(f"Config file {event.src_path} has been modified")
            self.load_config()


def start_watchdog(env_path, on_reload):
    event_handler = EnvHandler(env_path, on_reload)
    observer = PollingObserver()

    # Ensure the directory is correct and add some debug information
    directory = os.path.dirname(os.path.abspath(env_path))
    print(f"Monitoring directory: {directory}")

    observer.schedule(event_handler, path=directory, recursive=False)
    observer.start()

    def run_observer():
        observer.join()

    thread = threading.Thread(target=run_observer)
    thread.daemon = True
    thread.start()
