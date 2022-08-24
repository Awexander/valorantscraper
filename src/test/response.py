import aiohttp
import asyncio
import json

url = 'https://api.henrikdev.xyz/valorant/v1/website/en-us'

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10)) as session:
        async with session.get(url) as response:
            resp = await response.json()
            for r in resp['data']:
                if r['category'] == 'game_updates':
                    with open('data/test/response.json', 'w') as w:
                        json.dump(r, w, indent=4, separators=[',',':'])
                        break

asyncio.get_event_loop().run_until_complete(main())