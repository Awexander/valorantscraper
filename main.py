
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime
import getmatches as match
import requests
import json
import os

matchupdate = match.getmatchinfo()
intents = discord.Intents.default()
intents.members = True
intents.messages = True



updateURL = 'https://api.henrikdev.xyz/valorant/v1/website/en-us'
statusURL = 'https://api.henrikdev.xyz/valorant/v1/status/ap'
servername, logchannel = 723078810702184448, 1007170918549819412
uColor, red, green, blue = 0xffffff, 0xf50101, 0x01f501, 0x02aefd
prevUpdate, prevMaintenance, prevIncidents = '','',''

description: str= ''' valorant game updates, server status and scheduled maintenance '''

bot = commands.Bot(command_prefix='.', description=description, intents=intents)
isNeed_Notification = False
startTime = datetime.now()
connectionTime = datetime.now()
disconnetTime = datetime.now()
@bot.event 
async def on_disconnect():
    global disconnetTime
    disconnetTime = datetime.now()

@bot.event
async def on_resumed():
    global connectionTime
    connectionTime = datetime.now()
    await _log('[BOT]',f'bot is online') 

@bot.event
async def on_ready():
    global connectionTime, disconnetTime, prevUpdate, prevMaintenance, prevIncidents
    connectionTime = datetime.now()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=" raspberrypi "
            )
        )

    prevdata = await _readjson()
    try:
        prevUpdate = prevdata['updates']['title']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous updates details \n {error}')
    try:
        prevMaintenance = prevdata['maintenances']['title']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous maintenances details \n {error}')

    try:
        prevIncidents = prevdata['incidents']['title']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous incidents details \n {error}')

    await asyncio.sleep(1)
    dcTime = disconnetTime.strftime("%A %m/%d/%Y, %H:%M:%S")
    await _log('[BOT]',f'bot is online, \n disconnected since {dcTime}')
    loop.start()

@bot.after_invoke
async def on_command(ctx):
    if ctx.author == bot.user:
        return

    if isinstance(ctx.channel, discord.DMChannel):
        return await _log('[BOT]',f"got a direct message from <@{ctx.author.id}> \n '{ctx.message.content}'")
    
    await ctx.message.delete(delay=1)

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        return await _log('[BOT]',f"got a direct message from <@{message.author.id}> \n '{message.content}'")
    
@bot.command()
async def id(ctx):
    return await _log('[SERVER]',f'Channel ID: {ctx.channel.id}')

@bot.command()
async def uptime(ctx):
    upSeconds = datetime.now() - startTime
    connSeconds = datetime.now() - connectionTime
    
    upTime = await _getTimeElapsed(upSeconds)
    connTime = await _getTimeElapsed(connSeconds)

    return await _log('[SERVER]',f"[SERV TIME]\t {upTime} \n[BOT TIME]\t {connTime}")

@bot.command()
async def update(ctx):
    message = await _readjson()
    return await _log('[SERVER]', f"Latest update: {message['updates']['title']} \n Updated at: {message['updates']['date']}")

@bot.command()
async def lastmatch(ctx):
    result , error= await matchupdate.getmatches('awexander', '007')
    if result is True:
        latestmatch: str=f"Map: {matchupdate.match.map}, \t \t Mode: {matchupdate.match.gamemode} \n Score: {matchupdate.match.roundWon}-{matchupdate.match.roundLost}, Agent: {matchupdate.match.agent} \n Headshot: {int(round(matchupdate.match.headshot))} \n K/D: {float(round(matchupdate.match.kda, 2))} \n ADR: {int(round(matchupdate.match.adr))}"
        await _log('[SERVER]', f'{latestmatch}')
    else:
        await _log('[ERROR]', f'error loading latest match data \n {error}')

@tasks.loop(seconds=20)
async def loop():
    global prevUpdate, prevMaintenance, prevIncidents, isNeed_Notification
    updateData = await _requestsupdates(updateURL)
    maintenanceData, incidenctData = await _requestsupdates(statusURL)
    
    try:   
        latestPatch = await _getPatch(updateData)
        #print(f'{latestPatch}, {prevUpdate}')
        if latestPatch != prevUpdate and latestPatch != None:
            prevUpdate = latestPatch
            if updateData['external_link'] != None:
                link = updateData['external_link']
            else:
                link = updateData['url']
            isNeed_Notification = True

            #notification here
            if isNeed_Notification:
                await _log('[BOT]',f'new update is available')
                await _sendNotification(f"<@&{756538183810023564}> **GAME UPDATE** \n\n {updateData['title']} \n\n {link}")
                await _appendData(updateData, maintenanceData, incidenctData)

    except Exception as error:
        await _log('[ERROR]',f'processing updates data: \n{error}')

    try:
        if bool (maintenanceData):
            if maintenanceData['titles'] != prevMaintenance:
                await _log('[BOT]', maintenanceData)
    except Exception as error:
        await _log('[ERROR]',f'processing maintenances data: \n{error}')

    try:
        if bool(incidenctData):     
            if incidenctData['title'] != prevIncidents:
                await _log('[BOT]',f'{incidenctData}')
    except Exception as error:
        await _log('[ERROR]',f'processing incidents data: \n{error}')

async def _requestsupdates(url):
    try:
        resp = requests.get(url, timeout=10)
        if url == updateURL:
            return resp.json()['data'][0]
        elif url == statusURL:
            data = resp.json()['data']
            return data['maintenances'], data['incidents']

    except Exception as error:
       await _log('[ERROR]',f'requests failed: \n{error}')


async def _log(code, message):
    global uColor, red, green
    channel = bot.get_channel(logchannel)
    if code == '[ERROR]':
        uColor = red
    elif code == '[BOT]':
        uColor = green
    elif code == '[SERVER]':
        uColor = blue
    else:
        uColor = 0xffffff

    embed = discord.Embed(title=code,description=message, color=uColor)
    await channel.send(embed=embed)

async def _sendNotification(message):
    channel = bot.get_channel(servername)
    await channel.send(f'{message}')

async def _readjson():
    try:
        path = os.getcwd()
        with open(path +'/config/updates.json', 'r') as w:
            data = json.loads(w.read())
        return data
    except Exception as error:
        await _log('[ERROR]',f'failed to load updates file \n {error}')

async def _getPatch(data):
    if data['category'] == 'game_updates':
        return data['title']

async def _appendData(updateData, maintenanceData, incidenctData):
    try:
        path = os.getcwd()
        data = {           
            "updates": updateData,
            "maintenances": maintenanceData,
            "incidents": incidenctData
        }
        with open(path+'/config/updates.json', 'w') as w:
            w.write(json.dumps(data, indent=4, separators=[',',':']))
    except Exception as error:
        await _log('[ERROR]',f'error appending updates data \n {error}')
        
async def _getTimeElapsed(timeSeconds):
    minutes, seconds = divmod(timeSeconds.total_seconds(), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    upTime = []
    if days: 
        upTime.append('{:01}D '.format(int(days)))
    if hours:
        upTime.append('{:02}H '.format(int(hours)))
    if minutes:
        upTime.append('{:02}M'.format(int(minutes)))
    if seconds:
        upTime.append('{:02}S'.format(int(seconds)))

    return ':'.join(upTime)

bot.run(BOT_TOKEN)