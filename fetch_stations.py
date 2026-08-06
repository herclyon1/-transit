import requests, json

bbox = "34.27,135.09,35.06,135.78"
query = f"""[out:json][timeout:120];
node["railway"="station"]({bbox});
out body;"""

headers = {"User-Agent": "osaka-station-map-demo/0.1 (personal research)"}
last_err = None
for url in ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]:
    try:
        r = requests.post(url, data={"data": query}, headers=headers, timeout=180)
        r.raise_for_status()
        data = r.json()
        print(url, "-> elements:", len(data.get("elements", [])))
        with open("stations_raw.json", "w") as f:
            json.dump(data, f, ensure_ascii=False)
        break
    except Exception as e:
        last_err = e
        print(url, "failed:", e)
