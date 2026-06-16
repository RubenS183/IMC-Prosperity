import pandas as pd
import os
import re

def process_prosperity_data(directory='ROUND2'):
    prices_list = []
    trades_list = []
    
    # Get all files in the directory
    files = os.listdir(directory)
    
    # Regular expression to extract day from filename
    # matches 'prices_round_3_day_0.csv' or 'trades_round_3_day_0.csv'
    filename_re = re.compile(r'(prices|trades)_round_2_day_(\d+)\.csv')
    
    for filename in sorted(files):
        match = filename_re.match(filename)
        if not match:
            continue
            
        file_type = match.group(1)
        day = int(match.group(2))
        file_path = os.path.join(directory, filename)
        
        print(f"Processing {filename}...")
        
        # Read the CSV with semicolon delimiter
        df = pd.read_csv(file_path, sep=';')
        
        if file_type == 'prices':
            # Prices files already have a 'day' column
            # Add 1,000,000 to timestamp for each day
            df['timestamp'] = df['timestamp'] + (df['day'] * 1000000)

            prices_list.append(df)
            
        elif file_type == 'trades':
            # Trades files might not have a 'day' column, use the one from filename
            # Add 1,000,000 to timestamp for each day
            df['timestamp'] = df['timestamp'] + (day * 1000000)
            
            trades_list.append(df)
            
    # Concatenate all prices dataframes
    if prices_list:
        final_prices = pd.concat(prices_list, ignore_index=True)
        final_prices.to_csv('round2_prices.csv', index=False)
        print("Created round2_prices.csv")
    
    # Concatenate all trades dataframes
    if trades_list:
        # Some rows might be empty or problematic, we maintain the order
        final_trades = pd.concat(trades_list, ignore_index=True)
        final_trades.to_csv('round2_trades.csv', index=False)
        print("Created round2_trades.csv")

if __name__ == "__main__":
    process_prosperity_data()
