# IMC Prosperity Trading Context - VEV Options & Hydrogel Strategy

## 1. Portfolio & Products
- **Delta-1 Products:** `VELVETFRUIT_EXTRACT` (VEV), `HYDROGEL_PACK`.
- **Options (Vouchers):** 10 strikes labeled `VEV_4000` to `VEV_6500`.
- **Trading Limits:**
  - Vouchers: 300 each.
  - VEV Spot: 200.
  - Hydrogel: 200.

## 2. Market Observations (Day 3 Analysis)
- **Volatility Gap:** Realized Vol (~41%) is significantly higher than Implied Vol (~23%).
- **Market Implied Vol (IV):** Stabilizes around **22.6%** for near-ATM strikes (5000-5500). Initial fallback of 26% was too high, causing the trader to overpay for options.
- **Spot Behavior:** VEV spot is highly correlated with voucher price movements but trades with its own liquidity.
- **Liquidation:** Rounds end with liquidation at "hidden fair value" (likely Black-Scholes at market IV).

## 3. Strategy Implementation (`trader.py`)

### A. VEV Options (Vouchers)
- **Symmetric Market Making:** Quotes both Bid (⌊fv⌋ - 1) and Ask (⌈fv⌉ + 1) to capture spread.
- **Inventory Skew:** Quote sizes are adjusted based on current position relative to limits (pos/300) to ensure the position reverts to zero and stays within limits.
- **IV Estimation:** Uses a rolling 20-tick window of implied volatility calculated from the midpoint of market bids/asks.
- **Strike Classification:**
  - **MM Strikes (5000-5500):** Full market-making (30 units/side).
  - **ITM Strikes (4000, 4500):** Light market-making (8 units/side, wider spread).
  - **OTM Strikes (6000, 6500):** Lottery buys only (buy if price ≤ 1).

### B. Delta Hedging
- **Mechanism:** Maintains a delta-neutral portfolio by hedging the aggregate delta of all voucher positions using the `VELVETFRUIT_EXTRACT` spot.
- **Critical Fix:** Hedging is calculated based **ONLY** on actual filled positions (`state.position`). The previous bug included pending/unfilled orders, leading to massive over-hedging.
- **Target Position:** `VEV_Spot_Target = -Total_Option_Delta`.

### C. Hydrogel Pack
- **Strategy:** Pure symmetric market-making around the mid-price.
- **Inventory Skew:** Uses a ±3 tick skew to manage the 200-unit limit.
- **Note:** Removed previous "Mark 38" signal logic as it was underperforming.

## 4. Continuity & Persistence
- **TraderData:** Serializes `iv_hist` and `spot_hist` into a JSON string to maintain warm estimates between ticks and across round boundaries.
- **Time Convention:** Uses `252` trading days per year and `252e6` ticks per year.
- **Round Parameter:** `VEV_DAYS_LEFT` must be updated manually per round:
  - Round 1: 7
  - Round 2: 6
  - Round 3: 5
  - **Round 4: 4 (Current)**

## 5. Key Files
- `trader.py`: Active implementation including Black-Scholes class, MM logic, and delta hedging.
- `OLIVIA IS THE GOAT.py`: Reference for robust BS formulas and sample MM logic.
- `512203.log`: Historical performance log used to diagnose option losses and calibrate IV.

## 6. Known Gotchas
- **Gamma vs Theta:** High realized vol justifies the long-gamma exposure, but symmetric MM is preferred to mitigate theta decay during flat periods.
- **Hedge Headroom:** Keep an eye on VEV spot limits (200) as they can be hit quickly if multiple voucher positions move in the same direction.
