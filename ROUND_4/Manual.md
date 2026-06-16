I am participating in IMC Prosperity and I have given the guidelines and rules for the manual trading part of it. Go through it and make each of the blocks for an ipynb file that can simulate and analyze the below products with accurate simulations as mentioned in the rules to maximize profits. 

# Manual trading challenge: “Vanilla Just Isn’t Exotic Enough”

As the Intarian economy evolved, trading expanded beyond standard calls and puts. In this round, you can trade `AETHER_CRYSTAL`, vanilla options with 2 and 3 week expiries, and several exotic derivatives written on the same underlying.
Please note that a ‘week’ here refers to 5 trading days and that the ‘standard’ number of trading days per year is 252 (since some big exchanges are typically open 252 days per year). So “2 weeks” means 10 trading days, and “3 weeks” represents 15 trading days. For transparency purposes, this is how the days are computed on our end:

```python
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY

def weeks_to_years(weeks: float) -> float:
    # 5 business days per week, annualized to 252 trading days
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def steps_for_weeks(weeks: float) -> int:
    return int(round(weeks * 5 * STEPS_PER_DAY))

```

Thus, when you see "2 weeks", assume it means `2 * 5 * STEPS_PER_DAY` steps over 10 days.

Your objective is to construct positions that generate positive expected PnL. But be aware: unhedged exposure can lead to large losses, so risk management matters. The PnL is marked to the ‘fair’ value upon expiry, which is the average value of the product across 100 simulations. You should maximize the PnL on the products as you hold them till expiry if you buy (and short till expiry if you short). In other words, there is no buying or selling across days. You decide to buy/sell at t=0 (start of round 4) and hold it till expiry, at which point they are marked against their fair value. This means this challenge is completely standalone (there is NO relationship to Round 1).

All products are written on `AETHER_CRYSTAL`. You can trade the underlying, 2 week and 3 week vanilla calls and puts, and the following exotics:

<aside> ❓
Chooser Option
Expires in 3 weeks. After 2 weeks, the buyer chooses whether it becomes a call or a put, selecting whichever would be in the money at that time. It then behaves like a standard option for the final week until expiry.
</aside>

<aside> 🔀
Binary Put Option
Has an all-or-nothing payoff. If the underlying is below the strike at expiry, it pays the specified amount. Otherwise, it expires worthless.
</aside>

<aside> 🥊
Knock-Out Put Option
Behaves like a regular put unless the underlying ever trades below the knockout barrier before expiry. If the barrier is breached at any point, the option immediately becomes worthless.
</aside>

You may buy or sell up to the displayed volume in each product. Note that the “contract size” is 3000 across all products, and is only used as a way to scale PnL proportionally to Rounds 3 and 5; think of it as a PnL multiplier on the PnL you make on the individual products (underlying, options) listed in the table. The prices you see are for each individual option.

Your final score is the average PnL across 100 simulations of the underlying.
The underlying `AETHER_CRYSTAL` is simulated using Geometric Brownian Motion with zero risk-neutral drift and fixed annualized volatility of 251%. Prices evolve on a discrete grid of 4 steps per trading day, assuming 252 trading days per year (see code above). There is no ‘continuous’ modeling under the hood that could trigger a knock-out; you should only consider these discrete points.

And remember, when payoffs become conditional, so does risk. Good luck!
Note on “price” column: this is purely cosmetic and should show the ‘investment cost’, but is unrelated to your PnL. It should in no way afffect your trading decision, and you can freely ignore it.

The available options contracts are:

Option,Expiry,Size,Bid,Ask,Size,Buy/Sell,Price,Volume,Description
AETHER-CRYSTAL,N/A,200,49.975,50.025,200,,+0.71,,"Aether Crystals are precision-grown minerals formed under controlled electromagnetic conditions, used for energy stabilization in advanced systems."
AC_50_P,T + 21,50,12,12.05,50,,+2.71,,"Put option with strike price 50 XIRECs and expiry in 21 Solvenarian days."
AC_50_C,T + 21,50,12,12.05,50,,-0.45,,"Call option with strike price 50 XIRECs and expiry in 21 Solvenarian days."
AC_35_P,T + 21,50,4.33,4.35,50,,+0.42,,"Put option with strike price 35 XIRECs and expiry in 21 Solvenarian days."
AC_40_P,T + 21,50,6.5,6.55,50,,0.00,,"Put option with strike price 40 XIRECs and expiry in 21 Solvenarian days."
AC_45_P,T + 21,50,9.05,9.1,50,,-0.48,,"Put option with strike price 45 XIRECs and expiry in 21 Solvenarian days."
AC_60_C,T + 21,50,8.8,8.85,50,,+0.42,,"Call option with strike price 60 XIRECs and expiry in 21 Solvenarian days."
AC_50_P_2,T + 14,50,9.7,9.75,50,,+0.71,,"Put option with strike price 50 XIRECs and expiry in 14 Solvenarian days."
AC_50_C_2,T + 14,50,9.7,9.75,50,,+0.71,,"Call option with strike price 50 XIRECs and expiry in 14 Solvenarian days."
AC_50_CO,T + 14/21,50,22.2,22.3,50,,+0.71,,"Chooser option: after 14 days, becomes a put or call depending on which is in-the-money, then expires after 21 days total."
AC_40_BP,T + 21,50,5,5.1,50,,+0.71,,"Binary put: pays fixed 10 XIRECs if price < 40 at expiry, else worthless."
AC_45_KO,T + 21,500,0.15,0.175,500,,+0.71,,"Knock-out put: expires worthless if price drops below 35; otherwise behaves like standard put with strike 45."

# Clues

## Combining Vanillas and Exotics

Exotic options. Sure. They sound impressive. Attractive payoffs, interesting structures, the whole thing. And then you look a little closer and realize they are also sensitive to basically everything. The spot price. The timing. The exact path the underlying took to get there. All of it. Which is fine, until it isn't.

So before you get too attached to your exotic position, ask yourself whether part of that exposure could be replicated with vanilla options. Calls and puts are less spectacular, yes. Deliberately so. That is actually the point. Less spectacular usually means a bit easier to price. It means it does not suddenly behave differently because the underlying took an unexpected detour on the way to where you thought it was going.

Look at the exotic payoff on its own first. Then see what happens when you layer vanillas alongside it. Does the combination smooth out the extreme outcomes? Does it make the whole thing less dependent on one very specific scenario playing out perfectly? It usually does. Not always in a dramatic way. But enough to matter when things get weird.

The goal is not to turn your exotic into a vanilla. It is to build something around it that does not fall apart the moment conditions shift. Control the exposure. Do not let the exposure control you.

I’m going to stop right here. If I did any more explaining, it would look an awful lot like work.

## Choosing a Strategy for Chooser Options

Okay so a chooser option has two phases and they are not the same thing. Like, at all. Treating them like they are is how people end up confused and slightly poorer than they expected.

In the first phase you still get to decide whether the option becomes a call or a put. That flexibility is worth something. An actual measurable something. Ask yourself whether you could approximate that exposure using vanilla options. A combination of calls and puts might get you close enough to give you a useful reference point for what that optionality is actually worth right now. Which is good to know before you do anything else.

Then the decision window closes. And everything changes. The option type gets fixed and suddenly you are not dealing with open-ended flexibility anymore. You are dealing with a directional position that has a very specific opinion about where the underlying is going. That is a completely different situation and it needs a completely different approach.

So manage the two phases separately. What works in the first phase might not serve you well in the second. The transition is the part most people gloss over because it feels like a formality. It is not. It is the whole thing.

Two phases. Two frameworks. Don't mix them up. Please.

## Binary, Knock-Out and Risk

Right. These two. Pay attention because the risk in both of them is concentrated in a way that catches people off guard.

The binary put is all about one number. One threshold. Everything concentrates there. That kind of abrupt shift is very different from a standard put where the payoff changes gradually and gives you room to think. Here it does not. It just flips. Which is fine if you are positioned correctly and a little catastrophic if you are not.

The knock-out put is weirder. Its value does not just shift at a threshold. It can disappear entirely depending on how the underlying got there. Not where it ended up. How it traveled. A position that looked completely reasonable at entry can simply stop existing before it ever pays out. Cool feature. Terrible to be on the wrong side of it.

In both cases, think about whether vanilla options could soften the extreme scenarios. A well placed vanilla position can soften the binary cliff. It can cushion the knock-out risk before it becomes your whole problem. Yes, combining them reshapes the payoff. But a payoff you actually understand under bad conditions beats an elegant one that surprises you at the worst possible moment.

When payoffs are discontinuous, risk management stops being about direction and starts being about structure. Which is a more interesting problem, if you think about it. 