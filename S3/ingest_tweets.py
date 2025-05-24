import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import argparse
import math # For ceiling function in retry logic

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
TWITTER_API_URL = "https://api.twitter.com/2/tweets/search/recent"
DATA_DIR = Path("data")
REQUEST_TIMEOUT = 15
API_SLEEP_INTERVAL = 2 # Sleep between successful paginated requests
DEFAULT_MAX_TWEETS = 500
MAX_RESULTS_PER_PAGE = 100
MAX_RETRIES = 5 # Max retries for a single API call if rate limited
INITIAL_RETRY_DELAY = 60 # Initial delay in seconds for retry after 429

def search_recent_tweets(
    bearer_token: str,
    query: str,
    hours_ago: int = 24,
    max_tweets: int = DEFAULT_MAX_TWEETS,
    lang: str = "en"
) -> pd.DataFrame:
    if not bearer_token:
        print("Error: X_BEARER_TOKEN not found. Please set it in your .env file.")
        return pd.DataFrame()

    headers = {"Authorization": f"Bearer {bearer_token}"}
    start_time_dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    start_time_str = start_time_dt.isoformat().replace("+00:00", "Z")

    params = {
        "query": f"{query} lang:{lang}",
        "max_results": min(MAX_RESULTS_PER_PAGE, max_tweets),
        "start_time": start_time_str,
        "tweet.fields": "created_at,lang,author_id,public_metrics,source,geo,entities",
        "expansions": "author_id",
        "user.fields": "username,name,verified"
    }

    all_tweets_data = []
    users_data = {}
    next_token = None
    tweets_fetched_count = 0
    current_retries = 0

    print(f"Searching for tweets with query: '{query}'")
    print(f"Filtering for language: '{lang}', since: {start_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    while tweets_fetched_count < max_tweets:
        if next_token:
            params["pagination_token"] = next_token
        else:
            params.pop("pagination_token", None)
        
        remaining_to_fetch = max_tweets - tweets_fetched_count
        params["max_results"] = min(MAX_RESULTS_PER_PAGE, remaining_to_fetch)
        if params["max_results"] <= 0: break

        print(f"  Fetching page (current total: {tweets_fetched_count}, requesting: {params['max_results']})...")

        try:
            response = requests.get(TWITTER_API_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 429: # Rate limit hit
                current_retries += 1
                if current_retries > MAX_RETRIES:
                    print(f"  Max retries ({MAX_RETRIES}) reached for rate limit. Aborting.")
                    break
                
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header and retry_after_header.isdigit():
                    wait_time = int(retry_after_header)
                    print(f"  Rate limit hit. Header 'Retry-After' found. Waiting for {wait_time} seconds...")
                else:
                    # Exponential backoff with jitter
                    wait_time = INITIAL_RETRY_DELAY * (2 ** (current_retries - 1))
                    # Add some jitter (randomness to avoid thundering herd)
                    wait_time += math.ceil(wait_time * 0.1 * (os.urandom(1)[0] / 255.0)) 
                    print(f"  Rate limit hit. Waiting for {wait_time} seconds (attempt {current_retries}/{MAX_RETRIES})...")
                
                time.sleep(wait_time)
                continue # Retry the current page fetch

            response.raise_for_status() # Raise HTTPError for other bad responses (4xx or 5xx)
            data = response.json()
            current_retries = 0 # Reset retries on a successful request

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching tweets: {e}")
            if response is not None: print(f"  Response content: {response.text}")
            # Decide if you want to retry on general network errors or just break
            # For now, we break on general request exceptions other than 429
            break
        except ValueError: # Includes JSONDecodeError
            print("  Error decoding JSON response from Twitter API.")
            break # Don't retry on malformed JSON

        tweets_on_page = data.get("data", [])
        meta = data.get("meta", {})
        
        if "users" in data.get("includes", {}):
            for user in data["includes"]["users"]:
                users_data[user["id"]] = user

        if not tweets_on_page:
            print("  No more tweets found on this page or an issue occurred.")
            break

        for tweet in tweets_on_page:
            created_at_dt = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
            author_id = tweet.get("author_id")
            author_info = users_data.get(author_id, {})

            all_tweets_data.append({
                "tweet_id": tweet.get("id"), "created_at_utc": created_at_dt,
                "text": tweet.get("text"), "lang": tweet.get("lang"),
                "author_id": author_id, "author_username": author_info.get("username"),
                "author_name": author_info.get("name"), "author_verified": author_info.get("verified"),
                "retweet_count": tweet.get("public_metrics", {}).get("retweet_count"),
                "reply_count": tweet.get("public_metrics", {}).get("reply_count"),
                "like_count": tweet.get("public_metrics", {}).get("like_count"),
                "quote_count": tweet.get("public_metrics", {}).get("quote_count"),
                "source": tweet.get("source"),
                "hashtags": ", ".join([tag['tag'] for tag in tweet.get("entities", {}).get("hashtags", [])]),
                "mentions": ", ".join([mention['username'] for mention in tweet.get("entities", {}).get("mentions", [])]),
            })
            tweets_fetched_count += 1
            if tweets_fetched_count >= max_tweets: break
        
        next_token = meta.get("next_token")
        if not next_token or tweets_fetched_count >= max_tweets:
            print("  Reached max tweets or no more pages.")
            break
        
        if tweets_on_page: # Only sleep if we successfully got data and there's more to fetch
            time.sleep(API_SLEEP_INTERVAL)

    if not all_tweets_data:
        print("No tweets fetched that meet the criteria.")
        return pd.DataFrame()

    df = pd.DataFrame(all_tweets_data)
    df = df.sort_values(by="created_at_utc", ascending=False).reset_index(drop=True)
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search recent tweets using Twitter API v2.")
    parser.add_argument("--query", type=str, default="$BTC OR #Bitcoin -is:retweet", help="Twitter search query.")
    parser.add_argument("--hours", type=int, default=24, help="How many hours back to search (max 7 days).")
    parser.add_argument("--max_tweets", type=int, default=DEFAULT_MAX_TWEETS, help=f"Max tweets to fetch (default: {DEFAULT_MAX_TWEETS}).")
    parser.add_argument("--lang", type=str, default="en", help="Language code (e.g., 'en').")
    parser.add_argument("--initial_retry_delay", type=int, default=INITIAL_RETRY_DELAY, help="Initial delay (seconds) for retrying after a 429 error.")
    parser.add_argument("--max_retries", type=int, default=MAX_RETRIES, help="Max retries for rate limit errors.")

    args = parser.parse_args()

    # Update constants from args if provided
    INITIAL_RETRY_DELAY = args.initial_retry_delay
    MAX_RETRIES = args.max_retries


    if args.hours > 7 * 24:
        print("Warning: Twitter API v2 recent search typically covers up to the last 7 days. Adjusting hours to 168 (7 days).")
        args.hours = 168

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df_tweets = search_recent_tweets(
        bearer_token=X_BEARER_TOKEN,
        query=args.query,
        hours_ago=args.hours,
        max_tweets=args.max_tweets,
        lang=args.lang
    )

    if not df_tweets.empty:
        query_str_for_filename = "".join(filter(str.isalnum, args.query.split(" ")[0])).lower()
        if not query_str_for_filename: query_str_for_filename = "customquery"
        current_date_str = datetime.now().strftime("%Y%m%d")
        output_filename = DATA_DIR / f"{query_str_for_filename}_tweets_{current_date_str}.csv"
        
        try:
            df_tweets.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"\nSuccessfully saved {len(df_tweets)} tweets to {output_filename}")
        except IOError as e:
            print(f"Error saving tweets to CSV: {e}")
    else:
        print("\nNo tweets fetched, CSV file not created.")