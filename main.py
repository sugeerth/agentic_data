"""CLI entry point for VoyageAI Travel Planner."""

import argparse
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="VoyageAI - Multi-Agent AI Travel Planner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py --destination "Tokyo" --dates "2025-06-01 to 2025-06-07" --budget 3000
  python3 main.py --destination "Paris" --origin "London" --budget 2000 --travelers 2
  python3 main.py --destination "Bali" --dates "2025-08-15 to 2025-08-22" --budget 1500 --style adventure
        """,
    )

    parser.add_argument("--destination", "-d", required=True, help="Travel destination city")
    parser.add_argument("--origin", "-o", default="New York", help="Departure city (default: New York)")
    parser.add_argument("--dates", help='Travel dates as "YYYY-MM-DD to YYYY-MM-DD"')
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--budget", "-b", type=float, default=3000, help="Total budget in USD (default: 3000)")
    parser.add_argument("--travelers", "-t", type=int, default=1, help="Number of travelers (default: 1)")
    parser.add_argument("--preferences", "-p", default="balanced mix of culture, food, and adventure",
                        help="Travel preferences")
    parser.add_argument("--style", choices=["budget", "mid", "luxury"], default="mid",
                        help="Travel style (default: mid)")

    args = parser.parse_args()

    # Parse dates
    if args.dates:
        try:
            parts = args.dates.split(" to ")
            start_date = parts[0].strip()
            end_date = parts[1].strip()
        except (IndexError, ValueError):
            print("Error: Dates must be in format 'YYYY-MM-DD to YYYY-MM-DD'")
            sys.exit(1)
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        # Default: 30 days from now, 7 day trip
        from datetime import timedelta
        start = datetime.now() + timedelta(days=30)
        start_date = start.strftime("%Y-%m-%d")
        end_date = (start + timedelta(days=7)).strftime("%Y-%m-%d")

    preferences = args.preferences
    if args.style != "mid":
        preferences += f". Travel style: {args.style}"

    # Print banner
    print("\n" + "=" * 60)
    print("  VoyageAI - Multi-Agent AI Travel Planner")
    print("=" * 60)
    print(f"  Destination:  {args.destination}")
    print(f"  Origin:       {args.origin}")
    print(f"  Dates:        {start_date} to {end_date}")
    print(f"  Budget:       ${args.budget:,.2f}")
    print(f"  Travelers:    {args.travelers}")
    print(f"  Preferences:  {preferences}")
    print("=" * 60 + "\n")

    def cli_callback(agent_name, status, message):
        """Print agent updates to terminal."""
        if "Completed" in status:
            print(f"  [OK] {agent_name} agent completed")
        elif "Error" in status:
            print(f"  [!!] {agent_name} agent error: {status}")
        elif "compiled" in status:
            print(f"  [OK] Final itinerary compiled")

    try:
        from graph.workflow import run_travel_planner

        print("Starting multi-agent workflow...\n")

        itinerary = run_travel_planner(
            destination=args.destination,
            origin=args.origin,
            start_date=start_date,
            end_date=end_date,
            budget=args.budget,
            travelers=args.travelers,
            preferences=preferences,
            callback=cli_callback,
        )

        print("\n" + "=" * 60)
        print("  YOUR TRAVEL ITINERARY")
        print("=" * 60 + "\n")
        print(itinerary)

        # Save to file
        filename = f"itinerary_{args.destination.lower().replace(' ', '_')}.md"
        with open(filename, "w") as f:
            f.write(itinerary)
        print(f"\nItinerary saved to: {filename}")

    except ImportError as e:
        print(f"\nError: Missing dependency - {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure your OPENAI_API_KEY is set:")
        print("  export OPENAI_API_KEY=your_key_here")
        sys.exit(1)


if __name__ == "__main__":
    main()
