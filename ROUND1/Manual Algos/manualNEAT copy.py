import neat
import numpy as np
import random

# ----------------------------
# 1. HUMAN STRATEGIES
# ----------------------------

def strat_dumb():
    roll = np.random.random()
    if roll < 0.4:
        v = np.random.randint(5, 20)
    elif roll < 0.5:
        v = np.random.randint(60, 70)
    else:
        v = np.random.randint(30, 35)

    rem = 100 - v
    r = np.random.randint(0, rem + 1)
    return [r, rem - r, v]


def strat_below_avg():
    """
    Psychology: Values 'round' numbers and balanced splits.
    Doesn't understand logarithmic decay or rounding thresholds.
    """
    # Speed: Anchored to common round numbers or 'halfway' points
    v = np.random.choice([30, 40, 45, 50])
    
    rem = 100 - v
    # Thinking a 'balanced' approach is best for the remaining 
    # Usually splits 50/50 or 40/60 because 'Scale feels bigger'
    r_ratio = np.random.choice([0.4, 0.5])
    r = int(rem * r_ratio)
    s = rem - r
    
    return [r, s, v]

def strat_above_avg():
    """
    Psychology: Efficiency-focused. 
    1. Recognizes Research (x) log curve sweet spot (15-25%).
    2. Snipes Speed (z) at n+1 to beat the 'Below Average' crowd.
    3. Optimizes Scale (y) for rounding breakpoints.
    """
    # Speed: Snipes common anchors (41 instead of 40, 51 instead of 50)
    v = np.random.choice([41, 46, 51, 52])
    
    rem = 100 - v
    
    # 1. Research Sweet Spot: 
    # Log(21)/Log(101) is ~66% of max value for only 20% of budget.
    # They won't go much higher than 25 because the gains flatten.
    r = np.random.randint(18, 26)
    if r > rem: r = rem
    
    y_target = rem - r
    
    # 2. Scale Step Optimization:
    # Scale = round(7 * y/100, 1). 
    # They look for the lowest 'y' that hits the next 0.1 increment.
    best_y = 0
    current_val = round(7 * (y_target / 100), 1)
    # They might shave off 1 or 2 points of 'y' if it doesn't change the multiplier
    # and put it back into Research or just save it (though budget is usually spent).
    for y_test in range(y_target, 0, -1):
        if round(7 * (y_test / 100), 1) == current_val:
            best_y = y_test
        else:
            break
            
    # Any 'shaved' points go back to Research to crawl up the log curve
    r += (y_target - best_y)
    
    return [r, best_y, v]


def strat_high_iq():
    v = np.random.choice([i for i in range(46, 55)])
    rem = 100 - v

    best_y = 0
    max_scale_val = -1
    for y_test in range(rem + 1):
        scale_val = round(7 * (y_test / 100), 1)
        if scale_val >= max_scale_val:
            max_scale_val = scale_val
            best_y = y_test

    return [rem - best_y, best_y, v]


# ----------------------------
# 2. CORE UTILITIES
# ----------------------------

def clean_allocation(raw_outputs):
    """Convert NN outputs → valid integer % summing to 100"""
    vals = np.maximum(raw_outputs, 1e-6)
    vals = vals / np.sum(vals)

    perc = np.floor(vals * 100).astype(int)
    remainder = 100 - np.sum(perc)

    # distribute leftover
    for i in range(remainder):
        perc[i % 3] += 1

    return perc.tolist()


def get_speed_multipliers(z_values):
    """Proper rank with ties → linear 0.1 to 0.9"""
    N = len(z_values)

    # sort descending
    sorted_indices = np.argsort(z_values)[::-1]

    ranks = np.zeros(N, dtype=int)
    rank = 1

    for i, idx in enumerate(sorted_indices):
        if i > 0 and z_values[idx] != z_values[sorted_indices[i - 1]]:
            rank = i + 1
        ranks[idx] = rank

    multipliers = np.zeros(N)

    for i in range(N):
        if N == 1:
            multipliers[i] = 0.9
        else:
            multipliers[i] = 0.9 - (ranks[i] - 1) * (0.8 / (N - 1))

    return np.round(multipliers, 1)


def calculate_pnl(x, y, z, speed_mult):
    res_val = round(200000 * (np.log(x + 1) / np.log(101)))
    scale_val = round(7 * (y / 100), 1)

    gross = res_val * scale_val * speed_mult

    # convert % → actual spend
    cost = (x + y + z) * 500

    return gross - cost


# ----------------------------
# 3. NEAT EVALUATION
# ----------------------------

def eval_genomes(genomes, config):

    # ---- A. HUMAN POPULATION (9000) ----
    human_allocs = []
    for _ in range(1350): human_allocs.append(strat_dumb())
    for _ in range(3600): human_allocs.append(strat_below_avg())
    for _ in range(3150): human_allocs.append(strat_above_avg())
    for _ in range(900):  human_allocs.append(strat_high_iq())

    # ---- B. NEAT POPULATION ----
    neat_bots = []

    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)

        outputs = net.activate([1.0])
        x, y, z = clean_allocation(outputs)

        neat_bots.append({
            "genome": genome,
            "alloc": [x, y, z]
        })

    # ---- C. COMBINE FOR SPEED RANK ----
    all_z = [h[2] for h in human_allocs] + [b["alloc"][2] for b in neat_bots]
    speed_mults = get_speed_multipliers(all_z)

    # ---- D. ASSIGN FITNESS ----
    for i, bot in enumerate(neat_bots):
        x, y, z = bot["alloc"]

        speed = speed_mults[len(human_allocs) + i]

        fitness = calculate_pnl(x, y, z, speed)

        # stabilizing NEAT (avoid extreme negatives)
        bot["genome"].fitness = max(fitness, -1e6)


# ----------------------------
# 4. RUNNER
# ----------------------------

def run():

    import os
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, "config-neat.txt")

    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )

    pop = neat.Population(config)
    pop.add_reporter(neat.StdOutReporter(True))

    print("Running simulation...")
    winner = pop.run(eval_genomes, 300)

    # ---- FINAL STRATEGY ----
    net = neat.nn.FeedForwardNetwork.create(winner, config)
    out = net.activate([1.0])

    final = clean_allocation(out)

    print("\nOptimal Strategy:")
    print(f"Research: {final[0]}%")
    print(f"Scale:    {final[1]}%")
    print(f"Speed:    {final[2]}%")


if __name__ == "__main__":
    run()