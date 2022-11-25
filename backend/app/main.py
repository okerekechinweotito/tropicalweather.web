# application initilization starts here
import asyncio
import sys
from functools import wraps
from logging import info
from pathlib import Path

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from socketio.asyncio_namespace import AsyncNamespace

BASE = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE))

from app.schemas import PacketModel  # noqa: E402
from app.routers import location  # noqa: E402
from app.routers import weather  # noqa: E402
from app.utils import get_room_name, get_status  # noqa: E402
from app.database import engine, get_db  # noqa: E402
from app import models  # noqa: E402

models.Base.metadata.create_all(bind=engine)

# Application initilization
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Registering routes
app.include_router(weather.router)
app.include_router(location.router)


# Status page
def cache_response(func):
    """
    Decorator that caches the response of a FastAPI async function.
    """
    response = None

    @wraps(func)
    async def wrapper(*args, **kwargs):
        nonlocal response
        if not response:
            response = await func(*args, **kwargs)
    return wrapper


BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(Path(BASE_DIR, "templates")))


@app.get('/status', response_class=HTMLResponse)
@cache_response
async def status_page(request: Request):
    await asyncio.sleep(2)
    return templates.TemplateResponse(
        "status.html", get_status(request=request))


class AlertNameSpace(AsyncNamespace):
    # functions that have on_ prefix recognized as event
    async def on_connect(self, sid, *args, **kwargs):  # on connect event
        info(f"{sid}: Welcome!:)")

        query_string: str = args[0].get("QUERY_STRING", None)

        if not query_string:
            raise ConnectionRefusedError("Select a city and state")

        # Get the parameters from the query string
        query_string = query_string.split("&")
        query_string = {i.split("=")[0]: i.split("=")[1]
                        for i in query_string}

        state = query_string.get("state", None)
        city = query_string.get("city", None)

        self.room_name = get_room_name(city, state)

        self.enter_room(sid, self.room_name)

        # Add the location to the database
        db = next(get_db())
        try:
            db.add(models.Location(city=city, state=state))
            db.commit()
            print('commited')
        finally:
            db.close()

        info(f"Connected to {self.room_name}")

    async def on_packet(self, *args, **kwargs):  # on packet event

        # Packet Validation
        try:
            packet = PacketModel(**args[0])
        except ValidationError as ex:
            # Call-Back
            return PacketModel(
                content=str(ex.args), content_type="application/txt"
            ).dict()

        if not packet.content_type.startswith("application/json"):
            return PacketModel(
                content="Invalid content type",
                content_type="application/txt"
            ).dict()

        # Emit to name-space and room
        await self.emit(
            "message", packet.dict(),
            namespace=self.namespace,
            room=self.room_name
        )

        # Call-Back
        return PacketModel(
            content="Delivered", content_type="application/txt"
        ).dict()


# Message Queue is for working with distributed applications
mgr = socketio.AsyncRedisManager(
    "redis://localhost/0"
)

sio = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins="*"
)

# register the namespace
sio.register_namespace(
    AlertNameSpace("/Alert"))
asgi = socketio.ASGIApp(sio)


# mount Socket.Io to FastApi with / path
app.mount("/", asgi)
