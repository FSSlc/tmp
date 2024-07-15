from fastapi import FastAPI

from config import Settings, load_settings, start_watchdog

app = FastAPI()
settings: Settings = load_settings()


def reload_settings(new_settings: Settings):
    global settings
    settings = new_settings


# Start the watchdog to monitor config changes
start_watchdog(".env", reload_settings)


@app.get("/info")
async def get_info():
    return {
        "app_name": settings.app_name,
        "admin_email": settings.admin_email,
        "items_per_user": settings.items_per_user,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
