import pandas as pd
import numpy as np

def test_load():
    try:
        df = pd.read_csv("full_dataset.csv")
        print(f"Loaded dataset with {len(df)} rows.")
        print("Columns:", df.columns.tolist())
        
        # Calculate profiles
        if 'delhi_demand' in df.columns:
            # Group by day type and hour
            weekday_df = df[df['day_type'] == 'weekday']
            weekend_df = df[df['day_type'] != 'weekday'] # Handle 'weekend' or others
            
            # Avg hourly demand
            wd_profile = weekday_df.groupby('hour')['delhi_demand'].mean()
            we_profile = weekend_df.groupby('hour')['delhi_demand'].mean()
            
            print("\nWeekday Profile (First 5 hours):")
            print(wd_profile.head())
            print("\nWeekend Profile (First 5 hours):")
            print(we_profile.head())
            
            # Normalize? Optional, but absolute numbers are better for the "Total Pie" approach.
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_load()
