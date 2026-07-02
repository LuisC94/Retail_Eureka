import os
import sys
import torch
import numpy as np
import pandas as pd

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.path.append(current_dir)

from environment_pricing import PricingStockEnvironment
from agent.ppo_agent import ParallelPPOAgent

def get_pricing_suggestion(sku_name, current_state_dict, models_dir="models"):
    """
    Function to be imported and called inside Django/production applications.
    Accepts current state dictionary and returns recommended actions:
      - price_multiplier (0.5 to 1.5)
      - expose_quantity_percent (0.0 to 1.0)
    """
    state_dim = 17
    action_dim = 2
    
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim)
    agent.device = torch.device('cpu')
    
    checkpoint_dir = os.path.join(current_dir, models_dir)
    
    # Locate model checkpoint (supporting subdirectories, seeds and best dynamically)
    loaded = False
    import glob
    for base_name in [sku_name, "3_080"]:
        sku_folder = os.path.join(checkpoint_dir, base_name)
        search_paths = []
        if os.path.isdir(sku_folder):
            search_paths.append(sku_folder)
        search_paths.append(checkpoint_dir)
        
        for s_path in search_paths:
            actor_files = glob.glob(os.path.join(s_path, "*_actor.pth"))
            if not actor_files:
                actor_files = glob.glob(os.path.join(s_path, "**", "*_actor.pth"), recursive=True)
                
            if actor_files:
                matching_files = [f for f in actor_files if base_name in os.path.basename(f)]
                if not matching_files:
                    matching_files = actor_files
                
                # Sort to prefer models with highest episodes and seed42
                matching_files.sort(key=lambda f: ('ep20032' in f, 'seed42' in f, os.path.getmtime(f)), reverse=True)
                
                for best_file in matching_files:
                    checkpoint_path = best_file.replace('_actor.pth', '')
                    try:
                        agent.load(checkpoint_path)
                        loaded = True
                        break
                    except Exception:
                        pass
                if loaded:
                    break
        if loaded:
            break
                    
    agent.policy_old_actor.to('cpu')
    agent.policy_old_actor.eval()
    
    # Construct state vector from dict
    # Expected fields: stock_profile [G0..G3], total_stock, pred_today, pred_tomorrow, sales_t1, sales_t2,
    # price_today, price_history (last 15 days), temperature, humidity, ethylene
    # We construct the 17-D state using the exact formatting logic
    # In production, we can also query the environment directly if it holds historical context
    # Here, we assume state is already normalized or we construct it.
    # For a simpler fallback, if state is passed as a numpy array, we use it directly:
    if isinstance(current_state_dict, np.ndarray):
        state_tensor = torch.FloatTensor(current_state_dict).unsqueeze(0)
    else:
        # Construct state vector manually or pass dummy array if arguments are incomplete
        # For full safety, in Django we initialize the PricingStockEnvironment and query _get_state()
        raise ValueError("State must be a numpy array of 17 dimensions")
        
    with torch.no_grad():
        mean_percent, _ = agent.policy_old_actor(state_tensor)
        price_mult = 0.5 + 1.0 * torch.clamp(mean_percent[:, 0], 0.0, 1.0).item()
        qty_pct = torch.clamp(mean_percent[:, 1], 0.0, 1.0).item()
        
    return price_mult, qty_pct

def run_standalone_inference(sku_name="3_080"):
    print(f"=== RUNNING INFERENCE SIMULATION FOR SKU: {sku_name} ===")
    
    # Dataset path
    excel_name = f"m5_foods_{sku_name}.xlsx"
    if sku_name == "911753":
        excel_name = "911753_151dias_com_real.xlsx"
        
    excel_path = os.path.join(current_dir, "datasets", excel_name)
    if not os.path.exists(excel_path):
        excel_path = os.path.join(current_dir, "datasets", "m5_foods_3_080.xlsx")
        
    # Initialize env in testing split (remaining 40%)
    env = PricingStockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=500)
    state = env.reset()
    done = False
    
    total_profit = 0
    total_spoilage = 0
    days = 0
    
    while not done:
        price_mult, qty_pct = get_pricing_suggestion(sku_name, state)
        action = [price_mult, qty_pct]
        
        state, reward, done, info = env.step(action)
        total_profit += info['profit']
        total_spoilage += info['spoilage']
        days += 1
        
        if days % 10 == 0 or days == 1:
            print(f"Day {days:03d} | Suggestion: Price Mult = {price_mult:.3f}, Expose Qty% = {qty_pct:.3f} | Daily Profit = {info['profit']:.2f}€")
            
    print(f"\nSimulation complete over {days} days.")
    print(f"Total Profit: {total_profit:.2f}€ | Total Spoilage: {total_spoilage:.1f} kg")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", type=str, default="3_080", choices=["3_080", "911753", "3_252", "3_090", "3_586"])
    args = parser.parse_args()
    
    run_standalone_inference(args.sku)
