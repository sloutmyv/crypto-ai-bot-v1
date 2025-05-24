import os
import requests
import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import argparse # For command-line arguments

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")
BASE_URL = "https://cryptopanic.com/api/v1/posts/"
DATA_DIR = Path("data")
REQUEST_TIMEOUT = 15  # seconds
API_SLEEP_INTERVAL = 0.5  # seconds between API calls for different pages
DEFAULT_MAX_PAGES = 10 # Safety limit for pagination

def fetch_crypto_news(
    api_key: str,
    currencies: str | None = None, # e.g., "BTC" or "BTC,ETH"
    hours_ago: int = 24,
    kind: str = "news", # "news" or "media"
    max_pages: int = DEFAULT_MAX_PAGES
) -> pd.DataFrame:
    """
    Fetches news posts from CryptoPanic API for specified currencies and time window.

    Args:
        api_key: Your CryptoPanic API authentication token.
        currencies: Comma-separated list of currency codes (e.g., "BTC", "ETH").
                    If None, fetches general news (might not be what's usually desired).
        hours_ago: How many hours back to fetch news from.
        kind: Type of posts, "news" or "media".
        max_pages: Maximum number of pages to fetch to prevent excessive calls.

    Returns:
        A pandas DataFrame containing the news posts.
    """
    if not api_key:
        print("Error: CRYPTOPANIC_API_KEY not found. Please set it in your .env file.")
        return pd.DataFrame()

    news_items = []
    # Calculate the 'since' timestamp for client-side filtering
    since_cutoff_ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)

    params = {
        "auth_token": api_key,
        "kind": kind,
    }
    if currencies:
        params["currencies"] = currencies.upper() # API expects uppercase currency codes

    current_url = BASE_URL
    pages_fetched = 0

    print(f"Fetching '{kind}' for '{currencies if currencies else 'all'}' published since "
          f"{since_cutoff_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}, up to {max_pages} pages.")

    while current_url and pages_fetched < max_pages:
        pages_fetched += 1
        print(f"  Fetching page {pages_fetched} from: {current_url.split('?')[0]}...") # Show base URL for clarity

        try:
            # For the first request, params are added by requests.get()
            # For subsequent requests, current_url already contains all necessary query params from API's 'next' field
            response = requests.get(current_url, params=params if pages_fetched == 1 else None, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching page {pages_fetched}: {e}")
            break
        except ValueError: # Includes JSONDecodeError
            print(f"  Error decoding JSON response for page {pages_fetched}.")
            break

        results = data.get("results")
        if not results:
            print("  No 'results' found in API response for this page.")
            break

        stop_fetching_more_pages = False
        for post in results:
            published_at_str = post.get("published_at")
            title = post.get("title")

            if not published_at_str or not title:
                print(f"  Skipping post with missing 'published_at' or 'title': {post.get('id')}")
                continue

            post_ts = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            if post_ts < since_cutoff_ts:
                # If this post is too old, and API sorts by newest first,
                # all subsequent posts on this page and further pages will also be too old.
                print(f"  Post '{title[:30]}...' ({post_ts.strftime('%Y-%m-%d %H:%M')}) is older than cutoff. Stopping.")
                stop_fetching_more_pages = True
                break # Stop processing posts on this page

            news_items.append({
                "id": post.get("id"),
                "published_at_utc": post_ts,
                "title": title,
                "url": post.get("url"),
                "source_domain": post.get("source", {}).get("domain"),
                "source_title": post.get("source", {}).get("title"),
                "kind": post.get("kind"),
                "currencies_involved": ", ".join([c.get("code") for c in post.get("currencies", []) if c.get("code")]),
                "votes_positive": post.get("votes", {}).get("positive"),
                "votes_negative": post.get("votes", {}).get("negative"),
                "votes_important": post.get("votes", {}).get("important"),
                "votes_liked": post.get("votes", {}).get("liked"),
                "votes_disliked": post.get("votes", {}).get("disliked"),
                "votes_lol": post.get("votes", {}).get("lol"),
                "votes_toxic": post.get("votes", {}).get("toxic"),
                "votes_saved": post.get("votes", {}).get("saved"),
            })

        if stop_fetching_more_pages:
            break # Stop fetching subsequent pages

        current_url = data.get("next")
        if not current_url:
            print("  No more pages ('next' URL is null).")
            break
        
        if pages_fetched < max_pages: # Avoid sleeping if it's the last allowed page
             time.sleep(API_SLEEP_INTERVAL)


    if not news_items:
        print("No news items fetched that meet the criteria.")
        return pd.DataFrame()

    df = pd.DataFrame(news_items)
    # Sort by published_at_utc just in case, though API should provide them newest first
    df = df.sort_values(by="published_at_utc", ascending=False).reset_index(drop=True)
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch news from CryptoPanic API.")
    parser.add_argument(
        "--currencies",
        type=str,
        default="BTC", # Default to Bitcoin
        help="Comma-separated currency codes (e.g., 'BTC,ETH'). Fetches general news if omitted by API design, but this script defaults to BTC."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many hours back to fetch news from."
    )
    parser.add_argument(
        "--kind",
        type=str,
        default="news",
        choices=["news", "media"],
        help="Type of posts to fetch ('news' or 'media')."
    )
    parser.add_argument(
        "--max_pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum number of pages to fetch (default: {DEFAULT_MAX_PAGES})."
    )
    args = parser.parse_args()

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df_news = fetch_crypto_news(
        api_key=CRYPTOPANIC_API_KEY,
        currencies=args.currencies,
        hours_ago=args.hours,
        kind=args.kind,
        max_pages=args.max_pages
    )

    if not df_news.empty:
        # Create a filename based on currencies and current date
        currency_str_for_filename = args.currencies.replace(",", "-") if args.currencies else "general"
        current_date_str = datetime.now().strftime("%Y%m%d")
        output_filename = DATA_DIR / f"{currency_str_for_filename}_news_{args.kind}_{current_date_str}.csv"
        
        try:
            df_news.to_csv(output_filename, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
            print(f"\nSuccessfully saved {len(df_news)} headlines to {output_filename}")
        except IOError as e:
            print(f"Error saving data to CSV: {e}")
    else:
        print("\nNo data fetched, CSV file not created.")