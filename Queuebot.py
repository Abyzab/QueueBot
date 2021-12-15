import discord
from discord.ext import commands
import asyncio

class PycordManager(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents().all()
        super().__init__(command_prefix='~', intents=intents, case_insensitive=True)
        self.load_extension('Pycord')

    async def on_ready(self) -> None:
        print('Logged in as')
        print(super().user.name)
        print(super().user.id)
        print('------')

async def main():
    await PycordManager().start("<Place Discord Token Here>")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
