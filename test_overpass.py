import asyncio, httpx

async def main():
    headers = {'User-Agent': 'HeliosX/1.0', 'Accept': '*/*'}
    query = '[out:json];(way["building"](28.608,77.208,28.612,77.212););out body geom qt;'
    async with httpx.AsyncClient() as client:
        res = await client.post('https://overpass-api.de/api/interpreter', data={'data': query}, headers=headers)
        print('Status:', res.status_code)
        if res.status_code == 200:
            data = res.json()
            print('Elements:', len(data.get('elements', [])))
        else:
            print(res.text[:200])

asyncio.run(main())
