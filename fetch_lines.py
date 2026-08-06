import requests, json

bbox = "34.27,135.09,35.06,135.78"
# 旅客用軌道のみ: rail/subway/monorail/tram/light_rail, ヤード・側線除外
query = f"""[out:json][timeout:180];
(
  way["railway"~"^(rail|subway|monorail|tram|light_rail)$"]["service"!~"."]({bbox});
);
out tags geom;"""
headers = {"User-Agent": "osaka-station-map-demo/0.1 (personal research)"}
r = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers, timeout=240)
r.raise_for_status()
data = r.json()
print("ways:", len(data.get("elements", [])))
json.dump(data, open("lines_raw.json","w"), ensure_ascii=False)
