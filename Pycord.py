import json
from multiprocessing import Lock
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
        self._maxsize = int(maxsize)
        self.custom_id = custom_id
        self.update_queue()
        self._count = 0
        self.lock = Lock()

    def __getitem__(self, index: int) -> str:
        return self.queue[index]
    
    @property
    def maxsize(self) -> int:
        self.lock.acquire()
        size = self._maxsize
        self.lock.release()
        return size
    
    @maxsize.setter
    def maxsize(self, value) -> None:
        self.lock.acquire()
        self._maxsize = int(value)
        self.lock.release()
    
    @property
    def count(self) -> int:
        return self._count
    
    @count.setter
    def count(self, value: int) -> None:
        self.lock.acquire()
        self._count = value
        self.lock.release()

    def get_code(self) -> str:
        if self.code:
            return self.code
        linkcode = ""
        for x in range(8):
            linkcode += str(random.randint(0, 9))
        return linkcode
    
    def set_code(self, code: str) -> None:
        self.lock.acquire()
        self.code = code
        self.lock.release()

    def size(self) -> int:
        self.lock.acquire()
        size = len(self.queue)
        self.lock.release()
        return size

    def index(self, value: int) -> int:
        return self.queue.index(value)

    def append(self, item: int) -> bool:
        self.lock.acquire()
        self.queue.append(item)
        self.update_queue()
        self.lock.release()

    def __delitem__(self, index: int) -> None:
        self.lock.acquire()
        del self.queue[index]
        self.update_queue()
        self.lock.release()

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

    def correct_channel(ctx: commands.Context) -> bool:
        command_channel = ctx.bot.get_channel(920484222215553094) # Hard Coded Giveaway-Queue-Commands
        if ctx.channel == command_channel:
            return True
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

        self.queues.append(UserQueue(str(ctx.author.id), int(maxsize), unique_id.lower(), code))
        await ctx.send(f"Queue started for {ctx.author.mention}. Use .q {unique_id} to join!")
    
    @commands.command(aliases=['r'], brief = 
                    "Moves the queue along one person.")
    async def ready(self, ctx: commands.Context):
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        if queue.size() == 0:
            await ctx.send("There's no one to be ready for!")
            return

        user = self.bot.get_user(queue[0])
        del queue[0]

        if user is None:
            await ctx.send("User has left the server, please use .r again.")
            return

        next_user = False
        
        if queue.size() > 0:
            next_user = self.bot.get_user(queue[0])
            if next_user is None:
                del queue[0]
                return

        code = queue.get_code()

        await user.send(f"{ctx.author.mention} is waiting for you in on code: {code[:4]}-{code[4:]}")
        if queue.code:
            await ctx.send(f"{ctx.author.display_name}, {user.mention} is now up.")
        else:
            await ctx.author.send(f"{user.mention} is waiting for you on code: {code[:4]}-{code[4:]}")

        await ctx.message.add_reaction("👍")
        await ctx.send("Processing next in queue.")
        queue.count += 1

        if next_user:
            await next_user.send(f"Your turn is coming up for the {queue.custom_id} Giveaway next, please be ready.")
    
    @commands.check(correct_channel)
    @commands.command(aliases=['q', 'queue'], brief = 
                                "Adds you to the host's queue.")
    async def join(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that code does not match any currently running.")
            return

        if ctx.author.id in queue:
            await ctx.send(f"{ctx.author.mention}, you are already in the queue.")
            return

        if queue.closed:
            await ctx.send(f"{ctx.author.mention}, that queue is closed. Join failed.")
            return

        if queue.size() >= queue.maxsize:
            await ctx.send(f"{ctx.author.mention}, that queue is full. Join failed.")
            return
        
        await ctx.send(f"Added to {unique_id} Giveaway")


        queue.append(ctx.author.id)

        await ctx.send(f"{ctx.author.mention} has been added to the queue. Position: {queue.size()}.")
   
    @commands.check(correct_channel)
    @commands.command(aliases=['rq', 'lq', 'ql', 'leavequeue'], brief = 
                                "Removes you from the queue.")
    async def leave_queue(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that code does not match any currently running.")
            return

        if ctx.author.id not in queue:
            await ctx.send(f"{ctx.author.mention}, you are not currently in the queue.")
            return

        index = queue.index(ctx.author.id)
                
        del queue[index]

        await ctx.send(f"{ctx.author.mention} has been removed from the queue.")

    @commands.check(correct_channel)
    @commands.command(aliases=['qp', 'pq'], brief = 
                                "Posts your position in the host's queue.")
    async def queue_position(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that code does not match any currently running.")
            return

        if ctx.author.id not in queue:
            await ctx.send(f"{ctx.author.mention}, you are not currently in the queue.")
            return

        await ctx.send(f"{ctx.author.mention} is in the queue at position {queue.index(ctx.author.id) + 1}.")

    @commands.command(aliases=['qs', 'queuesize'], brief = 
                                "Posts the size of the host's queue.")
    async def queue_size(self, ctx: commands.Context, unique_id: str) -> None:
        queue = self.get_current_queue(unique_id.lower())

        if not queue:
            await ctx.send(f"{ctx.author.mention}, that code does not match any currently running.")
            return

        await ctx.send(f"The queue is currently {queue.size()} {'person' if queue.size() == 1 else 'people'}.")

    @commands.command(aliases=['p', 'c', 'pause', 'close'], brief = 
                                "Closes the host's queue for entry.")
    async def close_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        queue.close_queue()
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Closed for Entry.")

    @commands.command(aliases=['o', 'oq', 'open'], brief = 
                                "Opens the host's queue for entry.")
    async def open_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        queue.open_queue()
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Opened for Entry.")

    @commands.command(aliases=['s', 'stop'], brief = 
                                "Stops the Giveaway completely and removes it.")
    async def clear_queue(self, ctx: commands.Context) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return

        queue.clear_queue()
        self.queues.remove(queue)
        await ctx.send(f"Queue for {ctx.author.mention}'s Giveaway has been Cleared and Stopped.")
    
    @commands.command(aliases=['cc', 'code', 'setcode'], brief = 
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


    @commands.command(aliases=['remove', 'ru'], hidden=True)
    async def remove_user(self, ctx: commands.Context, member: discord.Member = None) -> None:
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"You're not currently hosting a Giveaway.")
            return

        if queue.size() == 0:
            await ctx.send(f"This queue has no one in it!")
            return
        
        id = member.id
        if member.id not in queue:
            await ctx.send("That user isn't in the queue.")
            return
        
        del queue[queue.index(id)]
        await ctx.send(f"{member.mention} has been removed from the queue.")


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
            embed['description'] += f'{i+1}. {queue} - {self.queues[i].custom_id} : {self.queues[i].size()} {"person" if self.queues[i].size() == 1 else "people"} in line.\n'

        await ctx.send(embed=Embed.from_dict(embed))
    
    @commands.command(aliases=['sent'], brief = "Displays the trades completed by host.")
    async def trades_sent(self, ctx: commands.Context) -> None:
        
        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return
        
        await ctx.send(f"{queue.count} {'trade' if queue.count == 1 else 'trades'} completed.")



    @commands.command(aliases=['cs', 'size'], brief = "Changes the maxsize of the queue.")
    async def change_size(self, ctx: commands.Context, maxsize: str) -> None:

        queue = self.get_current_queue(ctx.author.id, True)

        if not queue:
            await ctx.send(f"{ctx.author.mention}, you're not currently hosting a Giveaway.")
            return

        queue.maxsize = int(maxsize)

        await ctx.send(f"{ctx.author.mention}, queue maxsize updated.")

    # Error Handling

    @join.error
    @leave_queue.error
    @queue_position.error
    async def check_errors(self, error, ctx: commands.Context) -> None:
        print(type(error))
        if isinstance(error, commands.CheckFailure):
            await ctx.channel.send(f"{ctx.author.mention}, you can't use that in this channel.")


def setup(bot):
    bot.add_cog(MainCommands(bot))
