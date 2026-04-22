from breeze_connect import BreezeConnect
import datetime

# Step 1: Initialize Breeze client with your API key
breeze = BreezeConnect(api_key="4k97727977q8Z191_83e52X%7B413478")

# Step 2: Generate session using your API secret + daily session token
breeze.generate_session(
    api_secret="602qdw#86451s78O57K_C3h`!397817y",
    session_token="your_session_token"
)

# Step 3: Define today's date
today = datetime.date.today().strftime("%Y-%m-%d")

# Step 4: Example sector indices (replace with actual codes from ICICI Direct)
sector_indices = {
    "NIFTY IT": "NIFTYIT",
    "NIFTY BANK": "NIFTYBANK",
    "NIFTY FMCG": "NIFTYFMCG",
    "NIFTY AUTO": "NIFTYAUTO",
    "NIFTY PHARMA": "NIFTYPHARMA",
    "NIFTY ENERGY": "NIFTYENERGY",
    "NIFTY METAL": "NIFTYMETAL",
    "NIFTY REALTY": "NIFTYREALTY"
}

# Step 5: Fetch first 15 minutes OHLC data
performers = {}
for sector, code in sector_indices.items():
    data = breeze.get_historical_data(
        interval="1minute",
        from_date=f"{today}T09:15:00.000Z",
        to_date=f"{today}T09:30:00.000Z",
        stock_code=code,
        exchange_code="NSE",
        product_type="cash"
    )
    if data:
        open_price = float(data[0]['open'])
        close_price = float(data[-1]['close'])
        change_pct = ((close_price - open_price) / open_price) * 100
        performers[sector] = round(change_pct, 2)

# Step 6: Sort sectors by performance
sorted_perf = sorted(performers.items(), key=lambda x: x[1], reverse=True)

print("Top 3 Sector Performers (First 15 mins):")
for sector, perf in sorted_perf[:3]:
    print(f"{sector}: {perf}%")

print("\nBottom Sector:")
print(f"{sorted_perf[-1][0]}: {sorted_perf[-1][1]}%")