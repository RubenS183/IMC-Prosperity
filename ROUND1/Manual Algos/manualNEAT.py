import os
import neat
import numpy as np
import random

# --- 1. THE COMPETITION META (SIMULATED HUMANS) ---

def strat_dumb():
    roll = np.random.random()
    if roll < 0.4: v = np.random.randint(5, 20)  # Ignore Speed
    elif roll < 0.7: v = np.random.randint(60, 85) # Panic Speed
    else: v = np.random.randint(30, 35) # Noise
    rem = 100 - v
    r = np.random.randint(0, rem)
    return [r, rem - r, v]

def strat_below_avg():
    # Anchored to LLM common outputs (40-43)
    v = np.random.choice([40, 41, 43])
    rem = 100 - v
    # These users love "Scale" but don't optimize the rounding
    s = int(rem * 0.8)
    return [rem - s, s, v]

def strat_above_avg():
    # Anchored to competitive snipes (47-51)
    v = np.random.choice([47, 49, 51])
    rem = 100 - v
    # R ~ 25% of rem is a common 'smart' heuristic
    r = int(rem * 0.25)
    return [r, rem - r, v]

def strat_high_iq():
    # The Anti-Meta: Beats the 51% wall and optimizes Scale rounding
    v = np.random.choice([52, 53, 55])
    rem = 100 - v
    # They know the Scale formula: round(7 * y/100, 1)
    # They find the 'y' that gives the highest increment for the least cost
    best_y = 0
    max_scale_val = -1
    for y_test in range(rem + 1):
        scale_val = round(7 * (y_test / 100), 1)
        if scale_val >= max_scale_val:
            max_scale_val = scale_val
            best_y = y_test
    return [rem - best_y, best_y, v]

# --- 2. THE FITNESS ENGINE ---

def get_speed_multipliers(all_z_values):
    """Calculates multipliers for the entire pool of 10,000 players."""
    N = len(all_z_values)
    sorted_unique_z = sorted(list(set(all_z_values)), reverse=True)
    
    z_to_rank = {}
    current_rank = 1
    for z in sorted_unique_z:
        z_to_rank[z] = current_rank
        current_rank += all_z_values.count(z)
        
    multipliers = {}
    for z in sorted_unique_z:
        rank = z_to_rank[z]
        # Linear scale rank from 1/9 to 1
        rank_factor = 1.0 - (8/9) * ((rank - 1) / (N - 1)) if N > 1 else 1.0
        multipliers[z] = round(0.9 * rank_factor, 1)
    return multipliers

def calculate_pnl(x, y, z, speed_mult):
    res_val = round(200000 * (np.log(x + 1) / np.log(101)))
    scale_val = round(7 * (y / 100), 1)
    # We don't multiply by speed_mult here yet to keep logic clean
    gross = res_val * scale_val * speed_mult
    return gross - ((x + y + z) * 500)

# --- 3. NEAT INTEGRATION ---

def eval_genomes(genomes, config):
    # A. Generate Human Pool (9000 players)
    human_allocs = []
    for _ in range(1350): human_allocs.append(strat_dumb())
    for _ in range(3600): human_allocs.append(strat_below_avg())
    for _ in range(3150): human_allocs.append(strat_above_avg())
    for _ in range(900):  human_allocs.append(strat_high_iq())
    
    # B. Generate NEAT Pool (1000 players)
    neat_bots = []
    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        output = net.activate([1.0]) # Constant bias input
        # Softmax-style normalization to ensure 100% total
        raw = [max(0, o) for o in output]
        s = sum(raw) if sum(raw) > 0 else 1
        x, y, z = [int(round((v / s) * 100)) for v in raw]
        # Ensure constraint
        z = 100 - x - y
        neat_bots.append({'id': genome_id, 'genome': genome, 'alloc': [x, y, z]})
        
    # C. Combine and Rank Speed
    all_z = [b[2] for b in human_allocs] + [b['alloc'][2] for b in neat_bots]
    speed_map = get_speed_multipliers(all_z)
    
    # D. Assign Fitness
    for bot in neat_bots:
        x, y, z = bot['alloc']
        mult = speed_map[z]
        bot['genome'].fitness = calculate_pnl(x, y, z, mult)

# --- 4. RUNNER ---

def run_simulation():
    # Setup Config (Minimal version for brevity)
    # Ensure num_inputs=1, num_outputs=3 in your neat-config.txt
    config_path = "config-neat.txt" # Make sure this file exists!
    config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                         neat.DefaultSpeciesSet, neat.DefaultStagnation,
                         config_path)

    p = neat.Population(config)
    p.add_reporter(neat.StdOutReporter(True))
    
    print("Simulating 1,000 NEAT bots against 9,000 IQ-Tiered Humans...")
    winner = p.run(eval_genomes, 500)
    
    # Final Result
    net = neat.nn.FeedForwardNetwork.create(winner, config)
    out = net.activate([1.0])
    s = sum(out)
    final = [int(round((v / s) * 100)) for v in out]
    print(f"\nOptimal NEAT Strategy: Research {final[0]}%, Scale {final[1]}%, Speed {final[2]}%")

if __name__ == "__main__":
    run_simulation()