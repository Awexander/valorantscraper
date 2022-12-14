
import aiohttp
import datetime as dt
from src.CONFIG import NOMATCHPLAYED, SUCCESMATCH, FAILREQUEST

class getmatchinfo():
    def __init__(self):
        self.region = 'ap'
        self.matchlist = self._latestmatch(
            puuid=None,
            matchid=None, 
            map=None, 
            mode=None, 
            matchdate=None,
            agent=None, 
            rank=None, 
            roundWon=None, 
            roundLost=None, 
            headshot=None, 
            kda=None, 
            adr=None)
        pass
        
    async def getmatches(self, name, tag):
        self._name = name
        self._tag = tag
        self.matches = await self._request(name, tag)
        try:
            if self.matches.get('status') == 201:
                return NOMATCHPLAYED
                
            self.matchlist.matchid = await self._getMatchID()
            
            return SUCCESMATCH
        except:
            return FAILREQUEST

    async def processmatch(self):
        self.matchlist.map = await self._getmap()
        self.matchlist.gamemode = await self._getGameMode()
        self.matchlist.matchdate = await self._getmatchdate()

        self.matchstats = await self._getstats()
        self.matchlist.agent = await self._getAgent()
        self.matchlist.rank = await self._getRank()
        self.matchlist.roundWon, self.matchlist.roundLost = await self._getMatchResult()
        self.matchlist.headshot = await self._getHeadshot(self.matchstats)
        self.matchlist.kda = await self._getkda(self.matchstats)
        self.matchlist.adr = await self._getadr(self.matchstats)

    async def _request(self, name, tag):
        url = f'https://api.henrikdev.xyz/valorant/v3/matches/{self.region}/{name}/{tag}'
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30)) as session:
            async with session.get(url) as resp:
                matches = await resp.json()
                if matches['status'] == 200:
                    for data in matches['data']:
                        if data['metadata']['mode'] == 'Competitive':
                            return data
                        
                    return NOMATCHPLAYED
                else:
                    return matches

    async def fullmatch(self):
        data = []
        players = await self._getplayers()
        for player in players:
            self.matchstats = player
            playerData = {
                "puuid": player['puuid'],
                "name": player['name'],
                "tag": player['tag'], 
                "team": player['team'],
                "rank": player['currenttier_patched'],
                "agent": player['character'],
                "acs": await self._getacs(player),
                "headshot": await self._getHeadshot(player),
                "kda": await self._getkda(player),
                "adr": await self._getadr(player)
            }
            data.append(playerData)
        match = {
            "matchid": await self._getMatchID(),
            "map": await self._getmap(),
            "result": {
                "red": await self._getTeamResult('red'),
                "blue": await self._getTeamResult('blue')
            },
            "gamemode": await self._getGameMode(),
            "timeplayed": await self._getmatchdate(),
            "players": data
        }
        return match

    async def _getMatchID(self):
        return self.matches['metadata']['matchid']

    async def _getmap(self):
        return self.matches['metadata']['map']

    async def _getGameMode(self):
        return self.matches['metadata']['mode']
    
    async def _getmatchdate(self):
        timestamp = dt.datetime.fromtimestamp(self.matches['metadata']['game_start'])
        return timestamp.strftime("%B %d, %Y at %H:%M GMT+8")
    
    async def _getstats(self):
        for stats in self.matches['players']['all_players']:
            if stats['name'].lower() == self._name.lower() and stats['tag'].lower() == self._tag.lower():
                self.matchlist.puuid = stats['puuid']
                return stats

    async def _getplayers(self):
        return self.matches['players']['all_players']

    async def _getAgent(self):
        return self.matchstats['character']

    async def _getRank(self):
        url = f"https://api.henrikdev.xyz/valorant/v1/mmr/{self.region}/{self._name}/{self._tag}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30)) as session:
            async with session.get(url) as response:
                resp = await response.json()

                if resp.get('status') != 200:
                    return resp.get('status')
                
                return resp.get('data').get('currenttierpatched')

    async def _getMatchResult(self):
        team = self.matchstats['team'].lower()
        return self.matches['teams'][team]['rounds_won'], self.matches['teams'][team]['rounds_lost']

    async def _getTeamResult(self, team):
        return self.matches['teams'][team.lower()]['rounds_won']
    
    async def _getacs(self, player):
        return int(round(self.matchstats['stats']['score'] / self.matches['metadata']['rounds_played']))

    async def _getHeadshot(self, player):
        headshots = 0
        totalshots = 0

        for rounds in self.matches.get('rounds'):
            for plyr in rounds.get('player_stats'):
                if plyr.get('player_puuid') == player.get('puuid'):
                    for dmg_event in plyr.get('damage_events'):
                        if dmg_event.get('receiver_puuid') != player.get('puuid'):
                            headshots += dmg_event.get('headshots')
                            totalshots += (dmg_event.get('headshots') +
                                           dmg_event.get('bodyshots') + dmg_event.get('legshots'))
                    break

        return round((headshots / totalshots) * 100)

    async def _getkda(self, player):
        return [self.matchstats['stats']['kills'], self.matchstats['stats']['deaths'], self.matchstats['stats']['assists'], float(round(self.matchstats['stats']['kills'] / self.matchstats['stats']['deaths'],1))]
    
    async def _getadr(self, player):
        damage_made = 0
        for rounds in self.matches.get('rounds'):
            for plyr in rounds.get('player_stats'):
                if plyr.get('player_puuid') == player.get('puuid'):
                    for dmg_event in plyr.get('damage_events'):
                        if dmg_event.get('receiver_puuid') != player.get('puuid'):
                            damage_made += dmg_event.get('damage')
                    break

        return round(damage_made / self.matches.get('metadata').get('rounds_played'))
        
    class _latestmatch():
        def __init__(self, puuid, matchid, map, mode, matchdate, agent, rank, roundWon, roundLost, headshot, kda, adr):
            self.puuid = puuid
            self.matchid = matchid
            self.map = map
            self.gamemode = mode
            self.matchdate = matchdate
            self.agent = agent
            self.rank = rank
            self.roundWon = roundWon
            self.roundLost = roundLost
            self.headshot = headshot
            self.kda = kda
            self.adr = adr
