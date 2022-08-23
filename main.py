
import asyncio
from typing import Any
import discord
from discord.ext import commands, tasks
import datetime as dt
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
servername, logchannel, reportchannel, rankchannel = 1010443668659908788, 1007170918549819412, 1010808789680803871, 1011240037100310668
prevUpdate, prevMaintenance, prevIncidents = [],[],[]

description: str= ''' valorant game updates, server status and scheduled maintenance ''' 

bot = commands.Bot(command_prefix='.', description=description, intents=intents)
isNeed_Append = 'None'
startTime = dt.datetime.now()
connectionTime = dt.datetime.now()
disconnetTime = dt.datetime.now()

@bot.event 
async def on_disconnect():
    global disconnetTime
    disconnetTime = dt.datetime.now()

@bot.event
async def on_resumed():
    global connectionTime
    connectionTime = dt.datetime.now()
    await _log('[BOT]',f'bot is online') 

@bot.event
async def on_ready():
    global connectionTime, disconnetTime, prevUpdate, prevMaintenance, prevIncidents
    connectionTime = dt.datetime.now()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=" raspberrypi "
            )
        )

    prevUpdate, prevMaintenance, prevIncidents = await _readjson()

    await asyncio.sleep(1)
    dcTime = disconnetTime.strftime("%A %m/%d/%Y, %H:%M")
    await _log('[BOT]',f'bot is online, \n disconnected since {dcTime}')
    loop.start()
    getMatchReport.start()

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
    upSeconds = dt.datetime.now() - startTime
    connSeconds = dt.datetime.now() - connectionTime
    
    embed = discord.Embed(title='[SERVER]', color=0x02aefd)
    embed.add_field(name='SERVER TIME', value=await _getTimeElapsed(upSeconds), inline=False)
    embed.add_field(name='BOT TIME', value=await _getTimeElapsed(connSeconds), inline=False)

    await _sendlog(embed)

async def _sendlog(embed):
    channel = bot.get_channel(logchannel)
    return await channel.send(embed=embed)

@bot.command()
async def update(ctx):
    message = await _readjson()
    return await _log('[SERVER]', f"Latest update: {message['updates']['title']} \n Updated at: {message['updates']['date']}")

@bot.listen()
async def on_command_error(ctx, error):
    return await _log('[ERROR]', f'{error}')

@bot.command()
async def lastmatch(ctx, *,valorantid):
    #TODO: get lastmatch from db not from api
    nametag = valorantid.split('#')
    result , error= await matchupdate.getmatches(nametag[0], nametag[1])
    if result is True:
        content = {
        'map':matchupdate.match.map, 
        'mode':matchupdate.match.gamemode, 
        'score':f'{matchupdate.match.roundWon}-{matchupdate.match.roundLost}', 
        'agent':matchupdate.match.agent,
        'headshot':int(round(matchupdate.match.headshot)),
        'kda':matchupdate.match.kda,
        'adr':int(round(matchupdate.match.adr))
        }
        await _log('[REPORT]',message=f'**{valorantid.upper()}** \n Rank: {matchupdate.match.rank}',type='match', content=content)
    else:
        await _log('[ERROR]', f'error loading latest match data \n {error}')

@bot.command()
async def region(ctx, *, region):
    matchupdate.region = region
    return await _log('[SERVER]', f'Changed region to: {region}')
    
@tasks.loop(seconds=20)
async def loop():
    global prevUpdate, prevMaintenance, prevIncidents, isNeed_Append
    updateData = await _requestsupdates(updateURL)
    maintenanceData, incidentData = await _requestsupdates(statusURL)
    
    try:
        latestPatch = await _getPatch(updateData)
        if latestPatch['title'] != prevUpdate['title'] and latestPatch != None:
            prevUpdate = latestPatch
            if latestPatch['external_link'] != None:
                link = latestPatch['external_link']
            else:
                link = latestPatch['url']
            
            isNeed_Append = 'patch'
            await _log('[BOT]',f'new update is available')
            message= f"**GAME UPDATE** \n\n {latestPatch['title']} \n\n {link}"
            await _sendNotification(message, isNeed_Append, latestPatch, prevMaintenance, prevIncidents)
    except Exception as error:
        await _log('[ERROR]',f'processing updates data: \n{error}')

    try:
        if bool (maintenanceData):
            currMaintenance = await _getstatusData(maintenanceData)
            if currMaintenance['id'] != prevMaintenance['id'] and currMaintenance != None:
                prevMaintenance = currMaintenance

                isNeed_Append = 'maintenance'
                await _log('[BOT]',f'new maintenances updated')
                message= f"**MAINTENANCE UPDATE**\n\n**{currMaintenance['status'].upper()}: {currMaintenance['title']}**\n{currMaintenance['content']} \n\nUpdated at: {currMaintenance['time']}\nMore info: https://status.riotgames.com/valorant?region=ap&locale=en_US"
                await _sendNotification(message, isNeed_Append, prevUpdate, currMaintenance, prevIncidents)
    except Exception as error:
        await _log('[ERROR]',f'processing maintenances data: \n{error}')

    try:
        if bool(incidentData):
            currIncident = await _getstatusData(incidentData) 
            if currIncident['id'] != prevIncidents['id'] and currIncident != None:
                prevIncidents = currIncident
                
                isNeed_Append = 'incident'
                await _log('[BOT]',f'new incidents updated')
                message= f"**STATUS UPDATE**\n\n**{currIncident['severity'].upper()}: {currIncident['title']}**\n{currIncident['content']} \n\nUpdated at: {currIncident['time']}\nMore info: https://status.riotgames.com/valorant?region=ap&locale=en_US"
                await _sendNotification(message, isNeed_Append, prevUpdate, prevMaintenance, currIncident)
    except Exception as error:
        await _log('[ERROR]',f'processing incidents data: \n{error}')

@tasks.loop(minutes=30)
async def getMatchReport():
    try:
        with open('data/accounts.json', 'r') as r:
            ids = json.loads(r.read())
    except Exception as error:
        await _log('[ERROR]', message=f'error loading ids \n error')
    
    for id in ids:
        result, error = await matchupdate.getmatches(name=id['name'], tag=id['tag'])

        content = []
        if result is True:
            if matchupdate.match.matchid != id['matchid']:
                id['matchid'] = matchupdate.match.matchid
                content = {
                    'account': {
                        'name':id['name'], 
                        'tag':id['tag']
                    },
                    'rank':matchupdate.match.rank,
                    'map':matchupdate.match.map, 
                    'mode':matchupdate.match.gamemode, 
                    'timeplayed': matchupdate.match.matchdate,
                    'matchid': matchupdate.match.matchid,
                    'score':f'{matchupdate.match.roundWon}-{matchupdate.match.roundLost}', 
                    'agent':matchupdate.match.agent,
                    'headshot':int(round(matchupdate.match.headshot)),
                    'kda':matchupdate.match.kda,
                    'adr':int(round(matchupdate.match.adr))
                }
                await _matchReport('[REPORT]',message=f"**{id['name'].upper()}#{id['tag'].upper()}** \n Rank: {matchupdate.match.rank}",type='match', content=content)
            
                if matchupdate.match.rank != id['rank']:
                    id['rank'] = matchupdate.match.rank
                    await _matchReport('[REPORT]', message=f"**{id['name'].upper()}#{id['tag'].upper()}**", type='rank', content={'prevRank':id['rank'], 'currRank':matchupdate.match.rank})
                
                try:
                    matchlist = []
                    with open(f"data/accounts/{id['name']}#{id['tag']}.json", 'r') as r:
                        matchlist = json.loads(r.read())
                    
                    matchlist.insert(0, content)
                    try:
                        with open(f"data/accounts/{id['name']}#{id['tag']}.json", 'w') as w:
                            json.dump(matchlist, w, indent=4, separators=[',',':'])
                    except:
                        await _log('[ERROR]', message=f'error appending matchlist data \n {error}')
                    
                    try:
                        with open('data/accounts.json', 'w') as w:
                            json.dump(ids, w, indent=4, separators=[',',':'])
                    except Exception as error:
                        await _log('[ERROR]', f'error update accounts.json \n {error}')
                except Exception as error:
                    await _log('[ERROR]', f"error loading {id['name']}#{id['tag']}.json \n {error}")
        else:
            await _log('[ERROR]', f"error loading latest match data {id['name']}#{id['tag']} \n {error}")

async def _matchReport(code, message='', type='', content=Any):
    embed = discord.Embed(
        title=code,
        description=message, 
        color=0x02aefd,
    )
    if code == '[REPORT]':
        if type == 'match':
            channel = bot.get_channel(reportchannel)
            embed.add_field(name='MAP', value=content['map'], inline=True)
            embed.add_field(name='MODE', value=content['mode'], inline=True)
            embed.add_field(name='SCORE', value=content['score'], inline=True)
            embed.add_field(name='AGENT', value=content['agent'], inline=True)
            embed.add_field(name='K/D', value=float(content['kda'][3]), inline=True)
            embed.add_field(name='KDA', value=f"K:{content['kda'][0]} D:{content['kda'][1]} A:{content['kda'][2]}", inline=True)
            embed.add_field(name='ADR', value=content['adr'], inline=True)
            embed.add_field(name='HS%', value=f"{content['headshot']}%", inline=True)
            embed.set_footer(text=f"played on: {content['timeplayed']}")
        elif type == 'rank':
            channel = bot.get_channel(rankchannel)
            embed.add_field(name='Previous Rank', value=content['prevRank'])
            embed.add_field(name='Current Rank', value=content['currRank'])
    return await channel.send(embed=embed)

async def _getstatusData(data):
    for locale in data[0]['titles']:
        if locale['locale'] == 'en_US':
            incident = locale['content']
            break
    
    for translation in data[0]['updates'][0]['translations']:
        if translation['locale'] == 'en_US':
            content = translation['content']
            break
    content_id = data[0]['updates'][0]['id']
    strtime = data[0]['created_at']
    time = dt.datetime.strptime(strtime, "%Y-%m-%dT%H:%M:%S.%f%z") + dt.timedelta(hours=8)

    report = {
        'severity': data[0]['incident_severity'],
        'title': incident,
        'id': data[0]['id'],
        'content': content,
        'content_id': content_id,
        'time': time.strftime("%B %d, %Y at %H:%M GMT+8"),
        'status': data[0]['maintenance_status']
        }
    return report

async def _requestsupdates(url):
    try:
        resp = requests.get(url, timeout=10)
        if url == updateURL:
            return resp.json()
        elif url == statusURL:
            data = resp.json()['data']
            return data['maintenances'], data['incidents']

    except Exception as error:
       await _log('[ERROR]',f'requests failed: \n{error}')

async def _log(code, message='', type='', content=Any):
    uColor, red, green, blue = 0xffffff, 0xf50101, 0x01f501, 0x02aefd
    channel = bot.get_channel(logchannel)
    if code == '[ERROR]':
        uColor = red
    elif code == '[BOT]':
        uColor = green
    elif code == '[SERVER]' or '[REPORT]':
        uColor = blue
    
    embed = discord.Embed(
        title=code,
        description=message, 
        color=uColor
    )
    if code == '[REPORT]':
        if type == 'match':
            embed.add_field(name='MAP', value=content['map'], inline=True)
            embed.add_field(name='MODE', value=content['mode'], inline=True)
            embed.add_field(name='SCORE', value=content['score'], inline=True)
            embed.add_field(name='AGENT', value=content['agent'], inline=True)
            embed.add_field(name='K/D', value=float(content['kda'][3]), inline=True)
            embed.add_field(name='KDA', value=f"K:{content['kda'][0]} D:{content['kda'][1]} A:{content['kda'][2]}", inline=True)
            embed.add_field(name='ADR', value=content['adr'], inline=True)
            embed.add_field(name='HS%', value=f"{content['headshot']}%", inline=True)

    await channel.send(embed=embed)

async def _sendNotification(message, isNeed_Append, updateData, currMaintenance, currIncident):
    if isNeed_Append != 'None':
        _prevUpdate, _prevMaintenance, _prevIncidents = await _readjson()
        if isNeed_Append == 'patch': appendUpdate = updateData
        else: appendUpdate = _prevUpdate

        if isNeed_Append == 'maintenance': appendMaintenance = currMaintenance    
        else: appendMaintenance = _prevMaintenance

        if isNeed_Append == 'incident': appendIncident = currIncident
        else: appendIncident = _prevIncidents
        
        isNeed_Append = 'None'
        await _appendData(appendUpdate, appendMaintenance, appendIncident)

    channel = bot.get_channel(servername)
    await channel.send(f'<@&{756538183810023564}> {message}')

async def _readjson():
    try:
        path = os.getcwd()
        with open(path +'/data/updates.json', 'r') as w:
            data = json.loads(w.read())
    except Exception as error:
        await _log('[ERROR]',f'failed to load updates file \n {error}')

    try:
        prevUpdate = data['updates']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous updates details \n {error}')

    try:
        prevMaintenance = data['maintenances']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous maintenances details \n {error}')

    try:
        prevIncidents = data['incidents']
    except Exception as error:
        await _log('[ERROR]',f'failed to load previous incidents details \n {error}')
    
    return prevUpdate, prevMaintenance, prevIncidents

async def _getPatch(data):
    for patch in data['data']:
        if patch['category'] == 'game_updates':
            return patch

async def _appendData(updateData, maintenanceData, incidenctData):
    try:
        path = os.getcwd()
        data = {           
            "updates": updateData,
            "maintenances": maintenanceData,
            "incidents": incidenctData
        }
        with open(path+'/data/updates.json', 'w') as w:
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