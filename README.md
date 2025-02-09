# FIX Mini-Project

## Overview
This project is a FIX protocol-based trading application that handles order execution, PnL tracking and VWAP calculations. The system supports sending and cancelling orders while maintaining a structured order book.

## Features
**Execution Handling**: Tracks fills, partial fills, and rejections.

**PnL Calculation**: Computes realized and unrealized profit/loss.

**VWAP Calculation**: Tracks volume-weighted average price.

**Basic FIX Flows**: Logon, sequence number handling, heartbeat messages.

**Missing Fields Handling**: Added logic to detect and handle missing fields in execution reports to ensure accurate calculations.

## Technical Requirements
**FIX Version:** 4.2
**Python Version:** 3.9
**External Libraries:** quickfix
**Data Dictionary:** FIX42.xml

## Installation
Install dependencies: 
Prebuilt wheel used: quickfix-1.15.1-cp39-cp39-win_amd64.whl available at [Quickfix Wheel](https://github.com/kazcfz/QuickFIX-prebuilt-wheel)
Then in the terminal:
   ```
   pip install ~/Downloads/quickfix-1.15.1-cp39-cp39-win_amd64.whl
   ```

## Usage
### Start the application
```
./start.sh
```

Or manually:
```
cd src
python application.py client.cfg
```

## Order Execution
The application will send 1000 random orders (BUY, SELL, SELL SHORT) for MSFT, AAPL or BAC within 5 minutes
Orders may be limit or market orders
orders will be randomly cancelled throughout

## Supported FIX Messages

New Order (35=D): Sends limit or market orders.

Order Cancel Request (35=F): Requests order cancellation.

Reject (35=3): Handles rejected orders.

Execution Report (35=8): Tracks order execution states and ensures missing fields are accounted for.

Order Cancel Reject (35=9): Handles rejected cancellations.

## Trading Statistics
- Total Trading Volume (USD): Tracks the total volume of executed orders
- PnL (Profit and Loss): Tracks realised PnL of executed orders
- VWAP (Volume Weighted Average Price): Calculates market VWAP for each symbol
- Market statistics saved to src/market_stats.txt

## Example Output
```
============ MARKET STATS ============
VWAP for MSFT: 235.21258 USD
VWAP for AAPL: 148.59666 USD
VWAP for BAC: 50.40314 USD
Total Volume: 116407.10034 USD
PnL: 31975.73829 USD
=======================================
```

## Known Issues
- Add more detailed logging
- Execution reports 35=8 from server missing Avg_Px (6), CumQty(14) and LeavesQty (151)
- Required tag missing was bypassed by turning requirements in data dictionary from 'Y' to 'N'
- PnL not decrementing

