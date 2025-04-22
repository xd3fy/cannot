import os

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN env var not found!")
import discord
import re
import json
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio



# Initialize the bot instance
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Define your commands or event handlers here


# Assume 'active_games' is a global dictionary holding active games information
active_games = {}

# Function to create and manage the league match
@bot.tree.command(name="crnhostleague", description="Host a league match.")
@app_commands.choices(
    gametype=[
        app_commands.Choice(name="1v1", value="1v1"),
        app_commands.Choice(name="2v2", value="2v2"),
        app_commands.Choice(name="3v3", value="3v3"),
        app_commands.Choice(name="4v4", value="4v4")
    ],
    matchtype=[
        app_commands.Choice(name="Default Loadout", value="DL"),
        app_commands.Choice(name="Custom Loadout", value="CL"),
        app_commands.Choice(name="All Loadout", value="AL")
    ],
    region=[
        app_commands.Choice(name="NA", value="NA"),
        app_commands.Choice(name="EU", value="EU"),
        app_commands.Choice(name="ASIA", value="ASIA"),
        app_commands.Choice(name="OCE", value="OCE")
    ]
)
async def crnhostleague(interaction: discord.Interaction, gametype: str, matchtype: str, region: str, link: str):
    """Creates a private league thread."""
    
    guild = interaction.guild
    user = interaction.user
    category = interaction.channel
    
    # Check if the user already has an active league
   

    # Player caps for different game types
    player_caps = {"1v1": 2, "2v2": 4, "3v3": 6, "4v4": 8}
    player_cap = player_caps.get(gametype, 1000)
    
    # Create a private thread for the league match
    thread = await category.create_thread(name=f"League ({gametype}) - {user.name}", type=discord.ChannelType.private_thread, invitable=False)
    
    # Store match details in active_games
    active_games[user.id] = {
        "thread_id": thread.id,
        "gametype": gametype,
        "matchtype": matchtype,
        "region": region,
        "link": link,
        "player_cap": player_cap,
        "players": [user.id],
        "start_time": datetime.datetime.now()  # Store the start time of the league match
    }
    
    # Add the user to the thread
    await thread.add_user(user)
    
    # Get current time and format it
    current_time = datetime.datetime.now()
    start_time = active_games[user.id]["start_time"]
    time_diff = current_time - start_time
    
    if time_diff.days == 0:  # If within 24 hours
        formatted_time = current_time.strftime("Today at %H:%M")
    else:
        formatted_time = current_time.strftime("%d/%m/%Y %H:%M")
    
    # Game details to show in the embed
    game_details = (
        f"🏆 **Game Type:** {gametype}\n"
        f"⚙️ **Match Type:** {matchtype}\n"
        f"🌍 **Region:** {region}\n"
        f"🕒 **Hosted at:** {formatted_time}\n"
    )

    # Create the embed for the thread message
    thread_embed = discord.Embed(
        title="League Match Hosted!",
        description=f"League match hosted by {user.mention}",
        color=discord.Color.green()
    )
    thread_embed.add_field(name="Game Details", value=game_details, inline=False)
    thread_embed.add_field(name="Server Link", value=f"🔗 {link}", inline=False)
    
    # Send the embed in the thread (this is the only message to send now)
    await thread.send(embed=thread_embed)

    embed = discord.Embed(title="🟢 League Lobby Created", color=discord.Color.green())
    embed.add_field(name="📌 **Game Details:**", value=game_details, inline=False)
    embed.add_field(name="Hosted By", value=f"{user.mention}", inline=False)

    # ✅ Ping the League role
    league_role = discord.utils.get(guild.roles, name="League")
    if league_role:
        if league_role.mentionable:
            await category.send(f"{league_role.mention}", allowed_mentions=discord.AllowedMentions(roles=True))
        else:
            await category.send("!", allowed_mentions=discord.AllowedMentions(roles=True))

    # ✅ Attach the Join Button
    view = LeagueView(user.id, thread.id)  # Create Join League button view
    await interaction.response.send_message(embed=embed, view=view)  # Attach the button view

    # ✅ Log to the log channel by channel name "league-logs"
    try:
        log_channel = discord.utils.get(guild.text_channels, name="league-logs")
        if log_channel:
            log_embed = discord.Embed(
                title="🟢 League Match Hosted",
                description=f"New league match hosted by {user.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="🏆 Game Type", value=gametype, inline=True)
            log_embed.add_field(name="⚙️ Match Type", value=matchtype, inline=True)
            log_embed.add_field(name="🌍 Region", value=region, inline=True)
            log_embed.add_field(name="🕒 Hosted At", value=formatted_time, inline=False)
            log_embed.set_footer(text=f"Host ID: {user.id} | League Thread ID: {thread.id}")
            
            await log_channel.send(embed=log_embed)
        else:
            print("[Error Logging League] Could not find channel named 'league-logs'")

    except Exception as e:
        print(f"[Error Logging League] {e}")

async def delete_old_threads():
    """Check all active league threads and delete ones older than 1 hour."""
    await bot.wait_until_ready()  # Ensure bot is ready before starting the loop

    while True:
        for user_id, game_info in list(active_games.items()):
            thread_id = game_info.get("thread_id")
            if not thread_id:
                continue

            thread = bot.get_channel(thread_id)  # Get the thread object

            if thread and (datetime.datetime.now() - game_info["start_time"]).total_seconds() > 3600:
                try:
                    await thread.delete()  # Delete the thread if it’s older than 1 hour
                    print(f"Deleted thread {thread_id} (created by {user_id}) after 1 hour.")
                    del active_games[user_id]  # Remove the game from active games
                except discord.Forbidden:
                    print(f"Could not delete thread {thread_id}, missing permissions.")
                except discord.HTTPException as e:
                    print(f"HTTP error while deleting thread {thread_id}: {e}")

        await asyncio.sleep(60)  # Check every minute|


class LeagueView(discord.ui.View):
    """Interactive view for joining league matches."""

    def __init__(self, host_id, thread_id):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.thread_id = thread_id

    @discord.ui.button(label="Join League", style=discord.ButtonStyle.primary)
    async def join_league(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Try to fetch the thread by thread ID
        thread = interaction.guild.get_thread(self.thread_id) or bot.get_channel(self.thread_id)
        if not thread:
            await interaction.response.send_message("League thread not found. It may have been deleted.", ephemeral=True)
            return

        league_info = active_games.get(self.host_id)
        if not league_info:
            await interaction.response.send_message("This league match is no longer active.", ephemeral=True)
            return

        # Get the player count and exclude the bot ID from the count
        player_count = len([player for player in league_info.get("players", []) if player != bot.user.id])
        if player_count >= league_info.get("player_cap", float('inf')):
            await interaction.response.send_message("This league match is full.", ephemeral=True)
            return

        # Prevent players from joining multiple times
        if interaction.user.id in league_info["players"]:
            await interaction.response.send_message("You are already in this league match!", ephemeral=True)
            return

        try:
            await thread.add_user(interaction.user)
            league_info["players"].append(interaction.user.id)  # Add the user to the players list
            await interaction.response.send_message(f"You have joined {thread.mention}.", ephemeral=True)

            # Retrieve player information
            member = interaction.user
            rank_role = next((role.name for role in member.roles if role.name.startswith('R')), None)  # Get rank (R7 to R10)
            tier_role = next((role.name for role in member.roles if role.name in ["high", "mid", "low"]), None)  # Get tier (high, mid, low)
            region = league_info.get("region", "Unknown")  # Get region, default to "Unknown" if not set

            # Send embed message to the thread (without pinging them)
            embed_thread = discord.Embed(
                title=f"{member.name} has joined the League Match!",
                description=f"**Rank**: {rank_role} {tier_role}\n**Region**: {region}",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )
            embed_thread.set_footer(text="Join timestamp")
            await thread.send(embed=embed_thread, allowed_mentions=discord.AllowedMentions(users=False))

            # ✅ Get the guild from the interaction and log to the 'league-logs' channel
            guild = interaction.guild  # Access the guild from the interaction

            log_channel = discord.utils.get(guild.text_channels, name="league-logs")
            if log_channel:
                embed_log = discord.Embed(
                    title="✅ Player Joined League",
                    description=f"{member.mention} has joined a league match.",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed_log.add_field(name="Discord Name", value=f"{member.name}#{member.discriminator}", inline=True)
                embed_log.add_field(name="Rank", value=f"{rank_role} {tier_role}", inline=True)
                embed_log.add_field(name="Region", value=region, inline=True)
                embed_log.add_field(name="Thread", value=thread.mention, inline=False)
                embed_log.add_field(name="Host", value=f"<@{self.host_id}>", inline=False)
                embed_log.add_field(name="Current Players", value=f"{player_count + 1}/{league_info['player_cap']}", inline=False)  # Update current player count
                embed_log.set_footer(text=f"League ID: {self.host_id}")

                await log_channel.send(embed=embed_log)
            else:
                print("[League Log] Channel 'league-logs' not found.")

        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to add you to this league match.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to join the league match. Try again.", ephemeral=True)
        except Exception as e:
            print(f"[Error Logging Join] {e}")







       


        

@bot.tree.command(name="add", description="Add a user to the league thread (host only).")
async def add(interaction: discord.Interaction, member: discord.Member):
    """Allows the league host to add a player to the thread."""
    host_id = interaction.user.id
    game_info = active_games.get(host_id)

    if not game_info:
        await interaction.response.send_message("You are not hosting any league match.", ephemeral=True)
        return

    thread = interaction.guild.get_thread(game_info["thread_id"])
    if not thread:
        await interaction.response.send_message("League has ended!", ephemeral=True)
        return

    # Ensure there's space for more players
    if len(game_info["players"]) >= game_info["player_cap"]:
        await interaction.response.send_message("The league is full and cannot accept more players.", ephemeral=True)
        return

    # Add the player to the thread and the game info
    await thread.add_user(member)
    game_info["players"].append(member.id)

    # Get the player's region role and rank role
    region_role = None
    rank_role = None

    # Find the region role if it exists
    for role in member.roles:
        if role.name in ["NA", "EU", "ASIA", "OCE"]:  # Adjust region names to match your roles
            region_role = role.name
            break

    # Find the rank role if it exists
    rank_role = next((role.name for role in member.roles if role.name in ["Gold", "Platinum", "Diamond", "Unranked"]), "Unranked")

    # Embed with player information
    embed = discord.Embed(
        title=f"🎮 {member.name} Joined the League",
        description=f"{member.mention} has joined the league hosted by {interaction.user.mention}.",
        color=discord.Color.green()
    )
    embed.add_field(name="🔑 Discord Name", value=member.name, inline=False)
    embed.add_field(name="🌍 Region", value=region_role if region_role else "Not specified", inline=False)
    embed.add_field(name="🏅 Rank", value=rank_role, inline=False)
    embed.add_field(name="Thread", value=thread.mention, inline=False)

    # Send the embed in the thread
    await thread.send(embed=embed)

    # Log to the league-logs channel with embed
    log_channel = discord.utils.get(interaction.guild.text_channels, name="league-logs")
    if log_channel:
        log_embed = discord.Embed(
            title="📝 Player Joined League",
            description=f"{member.mention} has joined the league hosted by {interaction.user.mention} in {thread.mention}.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="Host", value=f"{interaction.user.mention}", inline=False)
        log_embed.add_field(name="League Thread", value=f"{thread.mention}", inline=False)
        log_embed.add_field(name="Discord Name", value=member.name, inline=False)
        log_embed.add_field(name="Region", value=region_role if region_role else "Not specified", inline=False)
        log_embed.add_field(name="Rank", value=rank_role, inline=False)
        log_embed.add_field(name="Total Players", value=f"{len(game_info['players'])}/{game_info['player_cap']}", inline=False)
        log_embed.set_footer(text="League Event")
        await log_channel.send(embed=log_embed)

    # Update player count and check if the player cap is reached
    if len(game_info["players"]) == game_info["player_cap"]:
        await thread.send("The league is now full!")
    
    await interaction.response.send_message(f"{member.mention} has been added to the league.", ephemeral=True)

@bot.tree.command(name="remove", description="Remove a player from the league.")
async def remove(interaction: discord.Interaction, member: discord.Member):
    """Removes a user from the league thread permanently."""
    thread = interaction.channel
    if not isinstance(thread, discord.Thread):
        await interaction.response.send_message("This command can only be used inside a league thread.", ephemeral=True)
        return
    
    # Ensure the member is part of the league
    game_info = active_games.get(interaction.user.id)
    if not game_info or member.id not in game_info["players"]:
        await interaction.response.send_message(f"This person is not in this league.", ephemeral=True)
        return

    try:
        # Remove the user from the thread and update the game info
        await thread.remove_user(member)
        game_info["players"].remove(member.id)
        
        # Send a simple message inside the thread
        await thread.send(f"{member.name} has been removed from the league.")

        # Log to the league-logs channel with embed
        log_channel = discord.utils.get(interaction.guild.text_channels, name="league-logs")
        if log_channel:
            log_embed = discord.Embed(
                title="🟠 Player Removed from League",
                description=f"{member.mention} has been removed from the league hosted by {interaction.user.mention}.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="Host", value=f"{interaction.user.mention}", inline=False)
            log_embed.add_field(name="League Thread", value=f"{thread.mention}", inline=False)
            log_embed.add_field(name="Removed Player", value=f"{member.mention}", inline=False)
            log_embed.set_footer(text="League Event")
            await log_channel.send(embed=log_embed)

        # Update the player cap and notify if the league has space
        if len(game_info["players"]) < game_info["player_cap"]:
            await thread.send(f"Someone has left the league. There is now space for more players!")

    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove this user.", ephemeral=True)
    except discord.HTTPException:
        await interaction.response.send_message("Failed to remove user. Try again.", ephemeral=True)



@bot.tree.command(name="leave", description="Leave the league thread.")
async def leave(interaction: discord.Interaction):
    """Allows players to leave the league thread and lose access."""
    thread = interaction.channel
    user = interaction.user

    if not isinstance(thread, discord.Thread):
        await interaction.response.send_message("This command can only be used inside a league thread.", ephemeral=True)
        return

    # Get host ID (from active_games)
    host_id = None
    for host, game in active_games.items():
        if game["thread_id"] == thread.id:
            host_id = host
            break

    if host_id is None:
        await interaction.response.send_message("This thread is not linked to an active league.", ephemeral=True)
        return

    
    try:
        # Remove user from thread and update player list
        await thread.remove_user(user)
        active_games[host_id]["players"].remove(user.id)

        # Send a simple message inside the thread
        await thread.send(f"{user.name} has left the league.")

        # Log to the league-logs channel with embed
        log_channel = discord.utils.get(interaction.guild.text_channels, name="league-logs")
        if log_channel:
            log_embed = discord.Embed(
                title="🟥 Player Left League",
                description=f"{user.mention} has left the league hosted by {interaction.user.mention}.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="Host", value=f"{interaction.user.mention}", inline=False)
            log_embed.add_field(name="League Thread", value=f"{thread.mention}", inline=False)
            log_embed.add_field(name="Left Player", value=f"{user.mention}", inline=False)
            log_embed.set_footer(text="League Event")
            await log_channel.send(embed=log_embed)

        # Update player cap and notify if needed
        if len(active_games[host_id]["players"]) < active_games[host_id]["player_cap"]:
            await thread.send(f"Someone has left the league. There is now space for more players!")

        # Revoke access (overwrite permissions)
        await thread.set_permissions(user, read_messages=False, send_messages=False)

        await interaction.response.send_message(f"You left the league and lost access.", ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove you from this thread.", ephemeral=True)
    except discord.HTTPException:
        await interaction.response.send_message("Failed to leave the league. Try again.", ephemeral=True)


@bot.tree.command(name="endgame", description="End the league and delete the thread.")
async def endgame(interaction: discord.Interaction):
    """Ends the league and deletes the thread."""
    host_id = interaction.user.id
    game_info = active_games.pop(host_id, None)

    if not game_info:
        await interaction.response.send_message("You are not hosting a league.", ephemeral=True)
        return

    thread = interaction.guild.get_thread(game_info["thread_id"])
    if not thread:
        await interaction.response.send_message("League thread not found.", ephemeral=True)
        return

    # Inform the host that the league was successfully ended
    await interaction.response.send_message("The league has been successfully ended and the thread will be deleted.", ephemeral=True)

    # Send a message in the thread before deletion
    await thread.send("League has ended!")

    # Wait a moment before deleting the thread (allows the message to be visible)
    await asyncio.sleep(2)
    await thread.delete()

    # Log to the league-logs channel with an embed
    log_channel = discord.utils.get(interaction.guild.text_channels, name="league-logs")
    if log_channel:
        log_embed = discord.Embed(
            title="🟥 League Ended",
            description=f"The league hosted by {interaction.user.mention} has ended and the thread was deleted.",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        log_embed.add_field(name="Host", value=f"{interaction.user.mention}", inline=False)
        log_embed.add_field(name="League Thread", value=f"{thread.mention}", inline=False)
        log_embed.set_footer(text="League Event")
        await log_channel.send(embed=log_embed)



import discord
import re

# Full rank role names mapping
RANK_TITLES = {
    "R1": "R1 - Peon",
    "R2": "R2 - Noob",
    "R3": "R3 - Rookie",
    "R4": "R4 - Cadet",
    "R5": "R5 - Striker",
    "R6": "R6 - Ronin",
    "R7": "R7 - Reaper",
    "R8": "R8 - Phantom",
    "R9": "R9 - Sentinel",
    "R10": "R10 - Vanguard"
}

TIER_ROLES = ["low", "mid", "high"]

@bot.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process only messages in the "rank-logs" channel
    if message.channel.name == "rank-logs":
        # Regex pattern explanation:
        # Group 1: user ID
        # Group 2: previous rank input (e.g. N/A, r1, R2, etc.)
        # Group 3: previous tier (e.g. low, mid, high) – optional
        # Group 4: new rank input
        # Group 5: new tier – optional
        pattern = r"<@!?(\d+)> (N/A|r[1-9]|r10|R[1-9]|R10)(?:\s+(low|mid|high))? to (N/A|r[1-9]|r10|R[1-9]|R10)(?:\s+(low|mid|high))?"
        match = re.match(pattern, message.content, re.IGNORECASE)
        
        if match:
            user_id = match.group(1)
            prev_rank_input = match.group(2).upper()  # e.g. "R1" or "N/A"
            prev_tier_input = match.group(3).lower() if match.group(3) else None
            new_rank_input = match.group(4).upper()     # e.g. "R1" or "N/A"
            new_tier_input = match.group(5).lower() if match.group(5) else None

            # If rank is N/A, ignore the tier input
            if prev_rank_input == "N/A":
                prev_tier_input = None
            if new_rank_input == "N/A":
                new_tier_input = None

            # Look up full role names from the mapping if applicable
            previous_full_role = RANK_TITLES.get(prev_rank_input) if prev_rank_input != "N/A" else None
            new_full_role = RANK_TITLES.get(new_rank_input) if new_rank_input != "N/A" else None

            # Get the member object
            user = discord.utils.get(message.guild.members, id=int(user_id))
            if user is None:
                return

            # For removal: if previous rank is N/A then there are no roles to check.
            if prev_rank_input != "N/A":
                prev_rank_role_obj = discord.utils.get(user.roles, name=previous_full_role)
                prev_tier_role_obj = discord.utils.get(user.roles, name=prev_tier_input) if prev_tier_input else None

                if prev_rank_role_obj is None or (prev_tier_input and prev_tier_role_obj is None):
                    await message.channel.send(
                        f"Error: {user.mention} does not currently have the rank {previous_full_role} "
                        f"{prev_tier_input if prev_tier_input else ''}. Please check the user's current rank and try again."
                    )
                    return
                # Remove the previous rank and tier roles
                try:
                    if prev_rank_role_obj and prev_tier_role_obj:
                        await user.remove_roles(prev_rank_role_obj, prev_tier_role_obj)
                    elif prev_rank_role_obj:
                        await user.remove_roles(prev_rank_role_obj)
                except Exception as e:
                    print(f"Error removing roles: {e}")
                    await message.channel.send(f"Error: Unable to remove roles for {user.mention}.")
            
            # If new rank is N/A, remove any rank/tier roles
            if new_rank_input == "N/A":
                for role in user.roles:
                    if role.name in RANK_TITLES.values():
                        try:
                            await user.remove_roles(role)
                        except Exception as e:
                            print(f"Error removing rank role {role.name}: {e}")
                for role in user.roles:
                    if role.name in TIER_ROLES:
                        try:
                            await user.remove_roles(role)
                        except Exception as e:
                            print(f"Error removing tier role {role.name}: {e}")
            else:
                # Add new roles
                new_rank_role_obj = discord.utils.get(message.guild.roles, name=new_full_role)
                new_tier_role_obj = discord.utils.get(message.guild.roles, name=new_tier_input) if new_tier_input else None
                if new_rank_role_obj and new_tier_role_obj:
                    try:
                        await user.add_roles(new_rank_role_obj, new_tier_role_obj)
                    except Exception as e:
                        print(f"Error adding roles: {e}")
                        await message.channel.send(f"Error: Unable to add roles to {user.mention}.")
            
            # Log the update in the 'rankbot-log' channel
            log_channel = discord.utils.get(message.guild.text_channels, name="rankbot-log")
            if log_channel:
                embed = discord.Embed(
                    title="Rank Update",
                    description=f"{user.mention} has had their rank updated.",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Previous",
                    value=f"{previous_full_role if previous_full_role else 'N/A'} {prev_tier_input if prev_tier_input else ''}".strip(),
                    inline=False
                )
                embed.add_field(
                    name="New",
                    value=f"{new_full_role if new_full_role else 'N/A'} {new_tier_input if new_tier_input else ''}".strip(),
                    inline=False
                )
                embed.add_field(name="Executed By", value=f"{message.author.mention}", inline=False)
                embed.set_footer(text=f"Rank update executed at {message.created_at}")
                await log_channel.send(embed=embed)
        else:
            print(f"Invalid rank change format: {message.content}")
    
    await bot.process_commands(message)

# ------------------ Rank Definitions ------------------
# Mapping of rank abbreviations to their full names.
rank_names = {
        "R1": "R1 - Peon",
    "R2": "R2 - Noob",
    "R3": "R3 - Rookie",
    "R4": "R4 - Cadet",
    "R5": "R5 - Striker",
    "R6": "R6 - Ronin",
    "R7": "R7 - Reaper",
    "R8": "R8 - Phantom",
    "R9": "R9 - Sentinel",
    "R10": "R10 - Vanguard"
}

# We only want to include players whose rank is R7 or higher.
allowed_rank_keys = ["R10", "R9", "R8", "R7"]
allowed_ranks = [rank_names[r] for r in allowed_rank_keys]

# Tiers remain unchanged
tier_roles = ["High", "Mid", "Low"]

def generate_role_hierarchy(ranks, tiers):
    """
    Generates a hierarchy for allowed rank-tier combinations.
    Lower numbers mean higher priority (e.g. R10 High is 1, R7 Low is last).
    """
    hierarchy = {}
    priority = 1
    for rank in ranks:  # Start from R10 down to R7
        for tier in tiers:        # High to Low
            key = f"{rank} {tier}"
            hierarchy[key] = priority
            priority += 1
    return hierarchy


role_hierarchy = generate_role_hierarchy(allowed_ranks, tier_roles)

# ------------------ Logging Helper ------------------
async def log_update(guild: discord.Guild, message: str):
    """
    Logs update messages to the 'rankbot-log' channel.
    """
    logs_channel = discord.utils.get(guild.text_channels, name="rankbot-log")
    if logs_channel:
        await logs_channel.send(message)

# ------------------ Roles Change Helper ------------------
def roles_changed(before_roles, after_roles):
    """
    Returns True if roles relevant to the leaderboard (allowed ranks or tier roles) have changed.
    """
    for role in set(before_roles) ^ set(after_roles):
        if role.name in allowed_ranks or role.name in tier_roles:
            return True
    return False

# ------------------ Manual Leaderboard Update ------------------
@bot.tree.command(name="updatetoplist", description="Updates the top players list in #top-players.")
async def update_top_players(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Acknowledge the interaction

    guild = interaction.guild
    top_players_channel = discord.utils.get(guild.text_channels, name="top-players")
    if not top_players_channel:
        await interaction.followup.send("❌ #top-players channel not found.")
        return

    role_players = []
    # Loop through guild members and include only those with an allowed rank and a tier.
    for member in guild.members:
        # Check if member has one of the allowed rank roles
        rank = next((r for r in allowed_ranks if discord.utils.get(member.roles, name=r)), None)
        # Check if member has one of the tier roles (High/Mid/Low)
        tier = next((t for t in tier_roles if discord.utils.get(member.roles, name=t)), None)
        if rank and tier:
            combined = f"{rank} {tier}"
            if combined in role_hierarchy:
                role_players.append((member, combined))
    
    if not role_players:
        await interaction.followup.send("⚠️ No players found with a rank of R7 or higher and a valid tier.")
        return

    # Sort the players using the defined role hierarchy (lower number = higher priority)
    role_players.sort(key=lambda x: role_hierarchy[x[1]])

    embed = discord.Embed(
        title="🏆 **Top Players Leaderboard** 🏆",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Updated just now.")

    for i, (member, role) in enumerate(role_players, 1):
        embed.add_field(name=f"{i}. {member.display_name}", value=f"Role: {role}", inline=False)

    # Look for an existing leaderboard message to update
    async for msg in top_players_channel.history(limit=10):
        if msg.author == bot.user and msg.embeds:
            if msg.embeds[0].title == "🏆 **Top Players Leaderboard** 🏆":
                await msg.edit(embed=embed)
                await interaction.followup.send("✅ Leaderboard updated!")
                await log_update(guild, f"Leaderboard updated manually by {interaction.user.display_name}.")
                return

    # If no existing leaderboard message, send a new one.
    await top_players_channel.send(embed=embed)
    await interaction.followup.send("✅ Leaderboard created!")
    await log_update(guild, f"Leaderboard created manually by {interaction.user.display_name}.")

# ------------------ Automatic Leaderboard Update ------------------
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """
    Automatically updates the leaderboard when a member's allowed rank or tier role is changed.
    Also, if a player drops below R7, they are removed from the leaderboard.
    """
    if not roles_changed(before.roles, after.roles):
        return

    guild = after.guild
    top_players_channel = discord.utils.get(guild.text_channels, name="top-players")
    if not top_players_channel:
        return

    role_players = []
    for member in guild.members:
        rank = next((r for r in allowed_ranks if discord.utils.get(member.roles, name=r)), None)
        tier = next((t for t in tier_roles if discord.utils.get(member.roles, name=t)), None)
        if rank and tier:
            combined = f"{rank} {tier}"
            if combined in role_hierarchy:
                role_players.append((member, combined))

    role_players.sort(key=lambda x: role_hierarchy[x[1]])

    embed = discord.Embed(
        title="🏆 **Top Players Leaderboard** 🏆",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Updated just now.")

    for i, (member, role) in enumerate(role_players, 1):
        embed.add_field(name=f"{i}. {member.display_name}", value=f"Role: {role}", inline=False)

    async for msg in top_players_channel.history(limit=10):
        if msg.author == bot.user and msg.embeds:
            if msg.embeds[0].title == "🏆 **Top Players Leaderboard** 🏆":
                await msg.edit(embed=embed)
                await log_update(guild, f"Leaderboard auto-updated due to role change for {after.display_name}.")
                return

    await top_players_channel.send(embed=embed)
    await log_update(guild, f"Leaderboard auto-created due to role change for {after.display_name}.")

# ------------------ Bot Initialization ------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot is online as {bot.user}")

# To run your bot, uncomment and replace YOUR_BOT_TOKEN with your actual bot token.
# bot.run('YOUR_BOT_TOKEN')


import os


HOST_STRIKED_ROLE = "Host Striked"
GRIEFING_STRIKE_ROLE = "Griefing Strike"
STRIKE_DATA_FILE = "strike_data_crn.json"  # Updated file name

# Load function for reading strike data from a JSON file
def load_strike_data():
    try:
        with open("strike_data_crn.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("No strike data found, starting fresh.")
        return {}
    except json.JSONDecodeError:
        print("Error decoding strike data, starting fresh.")
        return {}

# Save function for writing strike data to a JSON file
def save_strike_data(data):
    try:
        with open("strike_data_crn.json", "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving strike data: {e}")

# Loading strike data at the start
strike_data = load_strike_data()

# Assign roles based on strike type
async def assign_strike_role(user, guild, strike_type):
    role_name = HOST_STRIKED_ROLE if strike_type == "host" else GRIEFING_STRIKE_ROLE
    role = discord.utils.get(guild.roles, name=role_name)
    if role:
        await user.add_roles(role)


# Assume 'strike_data' holds the in-memory strike data
strike_data = {}


# Load strike data from the JSON file
def load_strike_data():
    try:
        with open("strike_data_crn.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save strike data to the JSON file
def save_strike_data(data):
    with open("strike_data_crn.json", "w") as f:
        json.dump(data, f, indent=4)

# Initialize strike_data from the file
strike_data = load_strike_data()

# Function to assign a strike role to the user when they reach 3 strikes
async def assign_strike_role(user, guild, strike_type):
    role_name = f"{strike_type.capitalize()} Strike"
    role = discord.utils.get(guild.roles, name=role_name)
    if role:
        await user.add_roles(role)
        print(f"Assigned {role_name} role to {user.name}.")
    else:
        print(f"{role_name} role not found in the guild.")

@bot.tree.command(name="strikemanagement", description="Manage user strikes.")
@app_commands.describe(
    action="Choose: add, remove, check",
    strike_type="Strike type: host or griefing (for adding/removing strikes)",
    amount="Number of strikes to add/remove (default 1, only for add/remove actions)",
    reason="Reason for the strike (optional, only for add/remove actions)",
    user="User to manage (required)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Add Strike", value="add"),
        app_commands.Choice(name="Remove Strike", value="remove"),
        app_commands.Choice(name="Check Strikes", value="check")
    ],
    strike_type=[
        app_commands.Choice(name="Host Strike", value="host"),
        app_commands.Choice(name="Griefing Strike", value="griefing")
    ]
)
async def strike(
    interaction: discord.Interaction,
    action: str,
    strike_type: str = None,
    amount: int = 1,
    reason: str = None,
    user: discord.User = None
):
    global strike_data

    # Ensure action is valid
    if action not in ["add", "remove", "check"]:
        await interaction.response.send_message("Invalid action. Choose from: add, remove, check.", ephemeral=True)
        return

    # Handle 'check' action: Only user required
    if action == "check":
        if user.id not in strike_data:
            strike_data[user.id] = {"host": [], "griefing": []}
        host_count = len(strike_data[user.id]["host"])
        grief_count = len(strike_data[user.id]["griefing"])
        embed = discord.Embed(
            title=f"Strike Overview for {user.name}",
            description=f"**Host Strikes**: {host_count}\n**Griefing Strikes**: {grief_count}",
            color=discord.Color.blue()
        )
        # Log the check action in strike-logs
        log_channel = discord.utils.get(interaction.guild.text_channels, name="strike-logs")
        if log_channel:
            embed.set_footer(text=f"Checked by {interaction.user.name}")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(embed=embed)
        return

    # Ensure user and strike type are valid for add/remove actions
    if user is None or strike_type not in ["host", "griefing"]:
        await interaction.response.send_message("Please provide a valid user and strike type (host or griefing).", ephemeral=True)
        return

    # Initialize user data if needed
    if user.id not in strike_data:
        strike_data[user.id] = {"host": [], "griefing": []}

    # Find the strike-logs channel
    log_channel = discord.utils.get(interaction.guild.text_channels, name="strike-logs")

    # Add strikes
    if action == "add":
        for _ in range(amount):
            strike_data[user.id][strike_type].append({
                "reason": reason,
                "added_by": interaction.user.name,
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        total = len(strike_data[user.id][strike_type])

        # Auto-role assignment if 3 or more strikes
        if total >= 3:
            await assign_strike_role(user, interaction.guild, strike_type)

        # Embed result message
        embed = discord.Embed(
            title=f"{strike_type.capitalize()} Strike Added",
            description=f"{user.mention} received **{amount}** {strike_type} strike(s). Total: **{total}**",
            color=discord.Color.red()
        )
        if reason:
            embed.add_field(name="Reason", value=reason)
        if log_channel:
            embed.set_footer(text=f"Action performed by {interaction.user.name}")
            await log_channel.send(embed=embed)

    # Remove strikes
    elif action == "remove":
        removed = 0
        for _ in range(amount):
            if strike_data[user.id][strike_type]:
                strike_data[user.id][strike_type].pop()
                removed += 1
        total = len(strike_data[user.id][strike_type])

        # Embed result message
        embed = discord.Embed(
            title=f"{strike_type.capitalize()} Strike Removed",
            description=f"{user.mention} had **{removed}** {strike_type} strike(s) removed. Total: **{total}**",
            color=discord.Color.green()
        )
        if log_channel:
            embed.set_footer(text=f"Action performed by {interaction.user.name}")
            await log_channel.send(embed=embed)

    # Save the updated strike data to the file
    save_strike_data(strike_data)

    # Respond to the user
    await interaction.response.send_message(embed=embed)




@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Global commands synced.")

bot.run(TOKEN)
