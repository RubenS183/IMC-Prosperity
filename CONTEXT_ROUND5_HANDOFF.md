# Round 5 Handoff Context

## Goal

Continue improving the Round 5 Prosperity trader using:

- `prices_combined.csv`
- `trades_combined.csv`
- `Round 5 Rules.md`
- `Algorithm Details.md`
- backtester logs shared by the user

Current trader file:

- [trader.py](/Users/rubenstalin/Desktop/IMC%20Prosperity/trader.py)

## Current Status

We started from a stale `trader.py` that referenced an old product and replaced it with a Round 5 trader.

Main iterations so far:

1. Broad market-making across many products.
   Result from [572584.log](/Users/rubenstalin/Desktop/IMC%20Prosperity/572584/572584.log): about `-34.8k`.

2. Reduced scope to strongest groups only:
   - `SLEEP_POD_*`
   - `MICROCHIP_*`
   - `SNACKPACK_*`
   - `UV_VISOR_*`

   Result from [572836.log](/Users/rubenstalin/Desktop/IMC%20Prosperity/572836/572836.log): about `+11.3k`.

3. Then expanded again with selective additional products and lag signals:
   - `PANEL_1X4`
   - `PANEL_2X4`
   - `TRANSLATOR_ASTRO_BLACK`
   - `OXYGEN_SHAKE_GARLIC`
   - `GALAXY_SOUNDS_SOLAR_FLAMES`
   - `GALAXY_SOUNDS_BLACK_HOLES`
   - `GALAXY_SOUNDS_SOLAR_WINDS`
   - `PEBBLES_*`

This expansion was coded into `trader.py`, but was not yet validated by a fresh uploaded backtest log in-chat.

## What The Logs Showed

### First weak version: `572584.log`

Total PnL:

- about `-34,788`

Worst groups:

- `ROBOT`
- `PEBBLES`
- `TRANSLATOR`
- `PANEL`
- `GALAXY_SOUNDS`
- `OXYGEN_SHAKE`

Best groups:

- `SLEEP_POD`
- `MICROCHIP`
- `UV_VISOR`
- `SNACKPACK`

Big issue:

- broad passive quoting caused adverse selection and large wrong-way inventory in trending products

### Better version: `572836.log`

Total PnL:

- about `+11,321.69`

Only traded groups in that version:

- `MICROCHIP`
- `SLEEP_POD`
- `SNACKPACK`
- `UV_VISOR`

Group PnL from that log:

- `MICROCHIP`: `+5150.9`
- `SLEEP_POD`: `+2792.4`
- `SNACKPACK`: `+1768.0`
- `UV_VISOR`: `+1610.3`
- others: `0.0`

Weak traded names in that log:

- `SLEEP_POD_LAMB_WOOL`: `-690.0`
- `UV_VISOR_RED`: `-440.0`
- `SNACKPACK_RASPBERRY`: `-230.8`

Strong traded names in that log:

- `MICROCHIP_SQUARE`: `+4208.0`
- `SLEEP_POD_POLYESTER`: `+1254.7`
- `UV_VISOR_MAGENTA`: `+880.5`
- `SLEEP_POD_SUEDE`: `+871.7`
- `MICROCHIP_CIRCLE`: `+828.5`
- `UV_VISOR_AMBER`: `+799.6`
- `SLEEP_POD_COTTON`: `+788.1`
- `SNACKPACK_STRAWBERRY`: `+740.0`
- `SNACKPACK_CHOCOLATE`: `+620.0`

## Useful Clues Already Investigated

User shared clues:

- “Same but Slower”
- “It’s a Lot”

Interpretation used:

- look for group structure first
- measure leader/laggard relationships
- avoid hard-coding to sample paths

What analysis found:

1. Group-level differences matter a lot.
   The strongest evidence so far was simply that some categories were consistently profitable while others were consistently bad for this style.

2. SNACKPACK has strong internal structure.
   Notable 1-tick delayed correlations:
   - `SNACKPACK_CHOCOLATE <-> SNACKPACK_VANILLA`: strong negative
   - `SNACKPACK_RASPBERRY <-> SNACKPACK_STRAWBERRY`: strong negative
   - `SNACKPACK_PISTACHIO <-> SNACKPACK_STRAWBERRY`: strong positive
   - `SNACKPACK_PISTACHIO <-> SNACKPACK_RASPBERRY`: strong negative

3. PEBBLES also has structure.
   - `PEBBLES_XL` is strongly negatively related to the other pebble products

4. Cross-category lead/lag was weak at the category-average level.
   The strongest results found were still small and mostly centered on `SNACKPACK`.

## Current Trader Design

`trader.py` currently contains:

- persistent `traderData` state
- online EWMA fair value
- volatility estimate
- inventory skew
- passive quoting logic
- per-product mark-to-market loss guards
- selective trading universe
- simple lag-edge adjustment for:
  - `SNACKPACK`
  - `PEBBLES`

Important current assumptions:

- no hard-coded prices
- no hard-coded timestamps
- no dependence on specific uploaded logs at runtime

## Files To Read First In A New Chat

1. [trader.py](/Users/rubenstalin/Desktop/IMC%20Prosperity/trader.py)
2. [572836.log](/Users/rubenstalin/Desktop/IMC%20Prosperity/572836/572836.log)
3. [572584.log](/Users/rubenstalin/Desktop/IMC%20Prosperity/572584/572584.log)
4. [Round 5 Rules.md](/Users/rubenstalin/Desktop/IMC%20Prosperity/Round%205%20Rules.md)
5. [Algorithm Details.md](/Users/rubenstalin/Desktop/IMC%20Prosperity/Algorithm%20Details.md)

## Recommended Next Step

In a new chat, ask the assistant to:

- inspect `trader.py`
- compare the current code against `572836.log`
- validate whether the newly added extra-product expansion improved or hurt PnL
- refine lag signals only where evidence is strong
- keep avoiding overfitting to one log

Suggested opener:

`Use CONTEXT_ROUND5_HANDOFF.md and continue improving trader.py for Round 5. Start by reading the current trader and the latest uploaded log, then decide whether the added extra products should stay.`
