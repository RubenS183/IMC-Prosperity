import math
import random
import numpy as np

# --- Constants ---
POPULATION_SIZE = 500
GENERATIONS = 150
MUTATION_RATE = 0.15
MAX_PERCENT = 100
COST_PER_PERCENT = 500

def generate_random_bot():
    """Generates a bot with random x, y, z percentages that sum to <= 100."""
    x = random.randint(0, 100)
    y = random.randint(0, 100 - x)
    z = random.randint(0, 100 - x - y)
    return [x, y, z]

def enforce_constraints(bot):
    """Ensures bot percentages are integers and do not exceed 100% total."""
    bot = [max(0, int(val)) for val in bot]
    while sum(bot) > 100:
        # Randomly reduce one of the non-zero pillars
        idx = random.choice([i for i, val in enumerate(bot) if val > 0])
        bot[idx] -= 1
    return bot

def get_speed_multipliers(population):
    """
    Ranks bots by Speed (z) and returns their multipliers.
    Highest z gets 0.9, lowest gets 0.1, scaled linearly.
    Equal investments share the same (highest) rank.
    """
    z_values = [bot[2] for bot in population]
    N = len(z_values)
    
    # Find unique z values and sort them descending to determine ranks
    sorted_unique_z = sorted(list(set(z_values)), reverse=True)
    z_to_rank = {}
    
    current_rank = 1
    for z in sorted_unique_z:
        z_to_rank[z] = current_rank
        current_rank += z_values.count(z) # Next rank skips by number of ties
        
    multipliers = []
    for z in z_values:
        rank = z_to_rank[z]
        # Linear scale: 0.9 for rank 1, down to 0.1 for rank N
        if N > 1:
            multiplier = 0.9 - 0.8 * ((rank - 1) / (N - 1))
        else:
            multiplier = 0.9
            
        # Rounding as requested by the prompt
        multipliers.append(round(multiplier, 1))
        
    return multipliers

def calculate_fitness(population):
    """Calculates the PnL for every bot in the population."""
    speed_multipliers = get_speed_multipliers(population)
    fitness_scores = []
    
    for i, bot in enumerate(population):
        x, y, z = bot[0], bot[1], bot[2]
        
        # 1. Research Edge (Logarithmic)
        research = round(200000 * (np.log(x + 1) / np.log(101)))
        
        # 2. Scale Multiplier (Linear with step rounding)
        scale = round(7 * (y / 100), 1)
        
        # 3. Speed Multiplier (Rank-based)
        speed = speed_multipliers[i]
        
        # 4. Budget Deduction
        budget_used = (x + y + z) * COST_PER_PERCENT
        
        # Final PnL Formula
        pnl = (research * scale * speed) - budget_used
        fitness_scores.append((pnl, bot))
        
    return fitness_scores

def crossover(parent1, parent2):
    """Creates a child by randomly combining genes from two parents."""
    child = [
        random.choice([parent1[0], parent2[0]]),
        random.choice([parent1[1], parent2[1]]),
        random.choice([parent1[2], parent2[2]])
    ]
    return enforce_constraints(child)

def mutate(bot):
    """Randomly tweaks a bot's allocation to introduce new genetic material."""
    if random.random() < MUTATION_RATE:
        idx = random.randint(0, 2)
        mutation_amount = random.randint(-10, 10)
        bot[idx] += mutation_amount
    return enforce_constraints(bot)

def run_simulation():
    # Initialize random population
    population = [generate_random_bot() for _ in range(POPULATION_SIZE)]
    
    for generation in range(GENERATIONS):
        # Evaluate fitness
        scored_population = calculate_fitness(population)
        
        # Sort by PnL (descending)
        scored_population.sort(key=lambda item: item[0], reverse=True)
        
        # Print top bot of every 10th generation to track progress
        if generation % 10 == 0 or generation == GENERATIONS - 1:
            best_pnl, best_bot = scored_population[0]
            print(f"Gen {generation:3} | Best Bot [Res: {best_bot[0]:2}%, Sca: {best_bot[1]:2}%, Spd: {best_bot[2]:2}%] | PnL: {best_pnl:,.0f} XIRECs")
            
        # Selection: Keep top 20% as parents
        parents = [bot for pnl, bot in scored_population[:int(POPULATION_SIZE * 0.2)]]
        
        # Elitism: Automatically carry over the top 5 bots unchanged
        next_generation = [bot for pnl, bot in scored_population[:5]]
        
        # Breed the rest of the population
        while len(next_generation) < POPULATION_SIZE:
            p1 = random.choice(parents)
            p2 = random.choice(parents)
            child = crossover(p1, p2)
            child = mutate(child)
            next_generation.append(child)
            
        population = next_generation

if __name__ == "__main__":
    print("Initializing Market Maker Bot Evolution...\n" + "-"*50)
    run_simulation()
    print("-" * 50)
    print("Simulation Complete.")