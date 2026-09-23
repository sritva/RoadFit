import time
import os
from playwright.sync_api import sync_playwright

def run_scenario(page, origin, dest, vehicle_label, rain_label, traffic_label, screenshot_name):
    print(f"\n--- Testing Scenario: {origin} -> {dest} | {vehicle_label.encode('ascii','ignore').decode()} | Rain: {rain_label.encode('ascii','ignore').decode()} | Traffic: {traffic_label.encode('ascii','ignore').decode()} ---")
    page.reload()
    page.wait_for_selector(".maplibregl-canvas")
    
    # Fill Origin
    orig_input = page.locator("input[placeholder='Search or click map…']").nth(0)
    orig_input.fill(origin)
    page.wait_for_selector(".dropdown-item")
    page.locator(".dropdown-item").first.click()
    time.sleep(1)
    
    # Fill Destination
    dest_input = page.locator("input[placeholder='Search or click map…']").nth(1)
    dest_input.fill(dest)
    page.wait_for_selector(".dropdown-item")
    page.locator(".dropdown-item").first.click()
    time.sleep(1)
    
    # Select Vehicle
    page.locator(f"button:has-text('{vehicle_label}')").click()
    
    # Select Rain
    page.locator(f"button:has-text('{rain_label}')").click()
    
    # Select Traffic
    page.locator(f"button:has-text('{traffic_label}')").click()
    
    # Click Calculate
    page.locator("button:has-text('Calculate Optimal Route')").click()
    
    try:
        # Wait for result stats
        page.wait_for_selector(".results-container", timeout=45000)
        time.sleep(2) # Let animation settle
        
        distance = page.locator("div.result-card >> text=Distance").locator("..").locator("span").nth(1).inner_text()
        eta = page.locator("div.result-card >> text=ETA").locator("..").locator("span").nth(1).inner_text()
        speed = page.locator("div.result-card >> text=Avg Speed").locator("..").locator("span").nth(1).inner_text()
        success = page.locator("div.result-card >> text=Success Probability").locator("..").locator("span").nth(1).inner_text()
        clearance = page.locator("div.result-card >> text=Min Clearance").locator("..").locator("span").nth(1).inner_text()
        
        print(f"Stats -> Dist: {distance}, ETA: {eta}, Speed: {speed}, Success: {success}, Clearance: {clearance}")
        
        screenshot_path = os.path.abspath(screenshot_name)
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved: {screenshot_name}")
    except Exception as e:
        print(f"Failed to get results: {e}")

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto("http://localhost:5173", timeout=30000)
        
        # Scenario 1: Baseline Hatchback
        run_scenario(page, "Koramangala", "Indiranagar", "🚗 Hatchback", "☀️ Clear", "🟢 Light", "test1_baseline.png")
        
        # Scenario 2: Delivery Van (Should have lower clearance & prob)
        run_scenario(page, "Koramangala", "Indiranagar", "🚛 Delivery Van", "☀️ Clear", "🟢 Light", "test2_van.png")
        
        # Scenario 3: Hatchback in Heavy Rain (Should have lower speed/prob)
        run_scenario(page, "Koramangala", "Indiranagar", "🚗 Hatchback", "⛈️ Heavy", "🟢 Light", "test3_rain.png")
        
        # Scenario 4: Hatchback in Gridlock Traffic (Should have much higher ETA, lower speed)
        run_scenario(page, "Koramangala", "Indiranagar", "🚗 Hatchback", "☀️ Clear", "🔴 Gridlock", "test4_gridlock.png")
        
        browser.close()

if __name__ == "__main__":
    verify_frontend()

