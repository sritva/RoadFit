import requests

def test_route(label, req):
    res = requests.post('http://127.0.0.1:8000/route/plan', json=req, timeout=30)
    d = res.json()
    if res.status_code != 200:
        print(f"[{label}] ERROR: {d}")
        return
    sr = d['selected_route']
    print(f"=== {label} ===")
    print(f"  Distance:   {sr['distance_km']} km")
    print(f"  ETA p50:    {sr['eta_p50_min']} min")
    print(f"  Avg Speed:  {sr['avg_speed_kmh']} km/h")
    print(f"  Cars/km:    {sr['avg_cars_per_km']}")
    print(f"  Success:    {sr['completion_probability']*100:.1f}%")
    print(f"  Clearance:  {sr['vehicle_clearance_margin_min_m']}m")
    print(f"  Coords:     {len(sr['geometry']['coordinates'])} points")
    print(f"  First pt:   {sr['geometry']['coordinates'][0]}")
    print(f"  Warnings:   {d['warnings']}")
    print()

base = {
    'orig_lat': 12.9345, 'orig_lon': 77.6220,
    'dest_lat': 12.9416, 'dest_lon': 77.6285,
    'vehicle_width': 1.8, 'vehicle_height': 1.6, 'vehicle_weight': 1.2,
    'rain_level': 'none', 'traffic_level': 'normal', 'simulate_congestion': False
}

test_route("Koramangala Hatchback - Clear", base)

rain_req = dict(base); rain_req['rain_level'] = 'heavy'
test_route("Koramangala Hatchback - Heavy Rain", rain_req)

traffic_req = dict(base); traffic_req['traffic_level'] = 'gridlock'
test_route("Koramangala Hatchback - Gridlock", traffic_req)

van_req = dict(base); van_req['vehicle_width'] = 2.4; van_req['vehicle_height'] = 2.8; van_req['vehicle_weight'] = 5.0
test_route("Koramangala Delivery Van - Clear", van_req)
