import json
import os
from discord import HTTPException, Forbidden, InvalidArgument
import discord
from discord.embeds import Embed
from discord.ext import commands
import random


class UserQueue:

    def __init__(self, id, maxsize: int, custom_id: str, code = False) -> None:
        self.dir_path = f"{os.path.dirname(os.path.realpath(__file__))}/queue.json"
        self.code = code
        self.host = id
        self.queue = []
        self.closed = False
        self.maxsize = int(maxsize)
        self.custom_id = custom_id
        self.update_queue()

    def __getitem__(self, index: int) -> str:
        return self.queue[index]
    
    def get_code(self) -> str:
        if self.code:
            return self.code
        linkcode = ""
        for x in range(8):
            linkcode += str(random.randint(0, 9))
        return linkcode
    
    def set_code(self, code: str) -> None:
        self.code = code

    def size(self) -> int:
        return len(self.queue)

    def index(self, value: int) -> int:
        return self.queue.index(value)

    def append(self, item: int) -> bool:
        self.queue.append(item)
        self.update_queue()

    def __delitem__(self, index: int) -> None:
        del self.queue[index]
        self.update_queue()

    def __contains__(self, item: int) -> bool:
        return item in self.queue

    def update_queue(self) -> None:
        with open(self.dir_path, 'r') as file:
            self.json = json.loads(file.read())
        if self.queue == []:
            self.json[f'{self.custom_id}'] = {str(self.host) : self.queue}

        self.json[f'{self.custom_id}'][f'{self.host}'] = self.queue
        with open(self.dir_path, 'w') as file:
            json.dump(self.json, file, indent=4)
        
    def close_queue(self):
        self.closed = True
    
    def open_queue(self):
        self.closed = False

    def clear_queue(self) -> None:
        with open(self.dir_path, 'r') as file:
            self.json = json.loads(file.read())
        del self.json[f'{self.custom_id}']
        with open(self.dir_path, 'w') as file:
            json.dump(self.json, file, indent=4)


class MainCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queues = []

    @commands.command()
    async def hi(self, ctx: commands.Context) -> None:
        await ctx.send(f"Hi ur qt {ctx.author.mention}!")

    def get_current_queue(self, id, is_host = False):
        if is_host:
            for queue in self.queues:
                if queue.host == str(id):
                    return queue 
        else:      
            for queue in self.queues:
                if queue.custom_id == id:
                    return queue
        return False
    
    def check_has_role(self, needed, roles):
        for role in roles:
            if role == needed or role.position > needed.position:
                return True
        return False

    @commands.command(aliases=['start'], hidden = True)
    async def create_queue(self, ctx: commands.Context, maxsize: int, unique_id: str, code :str = False):
        await ctx.message.delete()

        needed = discord.utils.get(ctx.guild.roles, name="Giveaway Host")

        perms = self.check_has_role(needed, ctx.author.roles)
            
        if not perms:
            await ctx.send("You don't have permission to run this command.")
            return
        
        if self.get_current_queue(ctx.author.id, True):
            await ctx.send("You've already got a queue running!")
            return

        if self.get_current_queue(unique_id):
            await ctx.send("A giveaway already exists with that unique ID.")
            return

        self.queues.append(UserQueue(str(ctx.author.id), maxsize, unique_id.lower(), code))
        await ctx.send(f"Queue started for {ctx.author.mention}. Use ~q {ctx.author.mention} to join!")
    
    @commands.command(aliases=['r'], description = 
                    "Moves the queue along one person.")
    async def ready(self, ctx: commands.Context):
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        if queue.size() == 0:
            await ctx.send("There's no one to be ready for!")
            return

        front = queue[0]
        user = self.bot.get_user(front)
        del queue[0]

        if user is None:
            await ctx.send("User has left the server, please use ~r again.")
            return
        
        code = queue.get_code()

        await user.send(f"{ctx.author.display_name} is waiting for you in Global Room {code[:4]}-{code[4:]}")
        if queue.code:
            await ctx.author.send(f"{user.display_name} is coming to your Room.")
        else:
            await ctx.author.send(f"{user.display_name} is waiting for you in Global Room {code[:4]}-{code[4:]}")

        await ctx.send("Processing next in queue.")


    @commands.command(aliases=['q', 'queue'], description = 
                                "Adds you to the host's queue.")
    async def add_queue(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that person is not currently hosting.")
            return

        if ctx.author.id in queue:
            await ctx.send(f"{ctx.author.mention}, you are already in the queue.")
            return

        if queue.closed:
            await ctx.send(f"{ctx.author.mention}, that queue is closed. Join failed.")
            return

        if queue.size() == queue.maxsize:
            await ctx.send(f"{ctx.author.mention}, that queue is full. Join failed.")
            return
        
        try:
            await ctx.author.send(f"Testing I can message you. Hello!")
        except (HTTPException, Forbidden, InvalidArgument):
            await ctx.send(f"{ctx.author.mention}, please enable direct messages to join the queue. Join failed.")
            return

        queue.append(ctx.author.id)

        await ctx.send(f"{ctx.author.mention} has been added to the queue. Position: {queue.size()}.")

    @commands.command(aliases=['rq', 'lq', 'ql', 'leavequeue'], description = 
                                "Removes you from the queue.")
    async def remove_queue(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that person is not currently hosting.")
            return

        if ctx.author.id not in queue:
            await ctx.send(f"{ctx.author.mention}, you are not currently in the queue.")
            return

        index = queue.index(ctx.author.id)
                
        del queue[index]

        await ctx.send(f"{ctx.author.mention} has been removed from the queue.")

    @commands.command(aliases=['qp', 'pq'], description = 
                                "Posts your position in the host's queue.")
    async def queue_position(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that person is not currently hosting.")
            return

        if ctx.author.id not in queue:
            await ctx.send(f"{ctx.author.mention}, you are not currently in the queue.")
            return

        await ctx.send(f"{ctx.author.mention} is in the queue at position {queue.index(ctx.author.id) + 1}.")

    @commands.command(aliases=['qs', 'queuesize'], description = 
                                "Posts the size of the host's queue.")
    async def current_queue_size(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that person is not currently hosting.")
            return

        await ctx.send(f"The queue is currently {queue.size()} {'person' if queue.size() == 1 else 'people'}.")

    @commands.command(aliases=['p', 'c', 'pause', 'close'], description = 
                                "Closes the host's queue for entry.")
    async def pause_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        queue.close_queue()
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Closed for Entry.")

    @commands.command(aliases=['o', 'oq', 'open'], description = 
                                "Opens the host's queue for entry.")
    async def open_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        queue.open_queue()
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Opened for Entry.")

    @commands.command(aliases=['s', 'stop'], description = 
                                "Stops the Giveaway completely and removes it.")
    async def close_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return

        queue.clear_queue()
        self.queues.remove(queue)
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Cleared and Stopped.")
    
    @commands.command(aliases=['cc', 'code', 'setcode'], description = 
                                "Allows the Host to change the Linkcode for the Room.")
    async def change_code(self, ctx: commands.Context, code:str) -> None:
        await ctx.message.delete()

        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return

        if len(code) != 8:
            await ctx.send(f"{ctx.author.mention}, that isn't a valid code.")
            return
        
        for letter in code:
            if letter not in ['0','1','2','3','4','5','6','7','8','9']:
                await ctx.send(f"{ctx.author.mention}, that isn't a valid code.")
                return

        queue.set_code(code)
        await ctx.send(f"Change completed.")
    
    @commands.command(aliases=['list'], hidden=True)
    async def queue_list(self, ctx: commands.Context, id: str = None) -> None:
        if id:
            queue = self.get_current_queue(id, True)
        else:
            queue = self.get_current_queue(ctx.author.id, True)
        needed = discord.utils.get(ctx.guild.roles, name="Discord Moderator")
        perms = self.check_has_role(needed, ctx.author.roles)

        if not queue:
            if id:
                await ctx.send("That's not a valid host.")
            else:
                await ctx.send(f"You're not currently hosting a Giveaway.")
            return

        if not perms and str(ctx.author.id) != queue.host:
            await ctx.send(f"You don't have permission to run this command.")
            return

        host = self.bot.get_user(int(queue.host))

        if queue.size() == 0:
            await ctx.send(f"This queue has no one in it!")
            return

        embed = {
            "color" : 0x82F1FC,
            "description" : ""
        }
        embed['title'] = f"{host.display_name}'s queue"
        for i in range(queue.size()):
            user = self.bot.get_user(queue[i])
            embed['description'] += f'{i+1}. {user.mention}\n'
        
        await ctx.send(embed=Embed.from_dict(embed))
    
    @commands.command(aliases=['aq'], hidden=True)
    async def active_queues(self, ctx: commands.Context) -> None:

        needed = discord.utils.get(ctx.guild.roles, name="Discord Moderator")
        perms = self.check_has_role(needed, ctx.author.roles)
        
        if not perms:
            await ctx.send(f"{ctx.author.mention}, you do not have permission to use this command.")
            return
        
        if len(self.queues) == 0:
            await ctx.send(f"No active queues!")
            return

        embed = {
            "color" : 0x82F1FC,
            "title" : "Current Giveaways Active",
            "description" : ""
        }

        for i in range(len(self.queues)):
            queue = self.bot.get_user(int(self.queues[i].host))
            embed['description'] += f'{i+1}. {queue}\n'

        await ctx.send(embed=Embed.from_dict(embed))


def setup(bot):
    bot.add_cog(MainCommands(bot))
