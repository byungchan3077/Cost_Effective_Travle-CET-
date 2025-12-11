import argparse
import sys
# Import Service
from services.travel_service import run_analysis_pipeline 

def main():
    # 1. Argument Parsing (Basic)
    parser = argparse.ArgumentParser(description="Cost Effective Travel - PPI Calculator.")
    parser.add_argument("--budget", type=float, required=True, help="Total travel budget")
    parser.add_argument("--days", type=int, required=True, help="Travel duration")
    args = parser.parse_args()

    # 2. Basic Validation
    if args.budget <= 0 or args.days <= 0:
        print("Error: Budget and days must be positive values (> 0).")
        sys.exit(1)

    # 3. Execute Service
    print(f"Running analysis for Budget: {args.budget}, Days: {args.days}...")
    results, status_message = run_analysis_pipeline(args.budget, args.days)

    # 4. Simple Output (For Logic Verification)
    if status_message == "Success":
        print("\n[Analysis Success]")
        for item in results:
            print(item) # Raw dictionary print
    else:
        print(f"\n[Analysis Failed] {status_message}")

if __name__ == "__main__":
    main()