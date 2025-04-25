import requests, datetime, random
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

@require_GET
def home(request):
    return render(request, "puzzles/index.html", {
        "puzzle": {
            "title": "Trend Trading Puzzle Simulator",
            "description": "Simulate trades on real uptrend/downtrend data from Binance."
        }
    })

@require_GET
def get_trend_puzzle(request):
    symbol        = request.GET.get("symbol", "BTCUSDT")
    desired_trend = request.GET.get("trend", "uptrend")
    interval      = "1m"
    cursor_key    = f"cursor:{symbol}:{desired_trend}"

    # Initialize or load our session cursor (ms since epoch)
    now_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
    end_ms = request.session.get(cursor_key, now_ms)

    # Step back exactly 1000 minutes
    batch_ms = 1000 * 60 * 1000
    start_ms = end_ms - batch_ms

    # Fetch that 1,000-candle slice
    resp = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={
            "symbol":    symbol,
            "interval":  interval,
            "startTime": start_ms,
            "endTime":   end_ms,
            "limit":     1000
        }
    )
    if resp.status_code != 200:
        return JsonResponse({"error":"Binance API failure"}, status=500)
    raw = resp.json()

    # Normalize to LightweightCharts format
    candles = [{
        "time":  k[0]//1000,
        "open":  float(k[1]),
        "high":  float(k[2]),
        "low":   float(k[3]),
        "close": float(k[4])
    } for k in raw]

    # Trend detection helpers
    def is_up(seg):
        return all(seg[i]["high"] > seg[i-1]["high"] and seg[i]["low"] > seg[i-1]["low"]
                   for i in range(1, len(seg)))
    def is_down(seg):
        return all(seg[i]["high"] < seg[i-1]["high"] and seg[i]["low"] < seg[i-1]["low"]
                   for i in range(1, len(seg)))

    window     = 30
    pre, trend = [], []
    for i in range(len(candles) - window + 1):
        seg = candles[i:i+window]
        if (desired_trend=="uptrend"   and is_up(seg)) or \
           (desired_trend=="downtrend" and is_down(seg)):
            pre   = candles[:i]
            trend = seg
            break

    if not trend:
        # Fallback: last window
        pre      = candles[:-window]
        trend    = candles[-window:]
        detected = "none"
    else:
        detected = desired_trend

    # Save cursor for next call
    request.session[cursor_key] = start_ms
    request.session.modified   = True

    return JsonResponse({
        "symbol":     symbol,
        "trend_type": detected,
        "pre_trend":  pre,
        "trend":      trend
    }, safe=False)
