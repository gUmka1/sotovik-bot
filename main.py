import asyncio
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from api import app
from bot import dp, bot, scheduler


async def run_bot():
    await dp.start_polling(bot)


async def main():
    await init_db()

    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        run_bot(),
        scheduler(),
    )


if __name__ == "__main__":
    asyncio.run(main())
