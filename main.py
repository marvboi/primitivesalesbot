import os
import time
import json
import requests
import tweepy
import schedule
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Reservoir API Configuration
RESERVOIR_API_KEY = os.getenv("RESERVOIR_API_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x424d781e0163b5a42ca2f27d036c2d5c561022c3")
# Base-specific Reservoir API endpoint
RESERVOIR_BASE_URL = "https://api-base.reservoir.tools"

# Twitter API Configuration
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Configure how often to check for new sales (in seconds)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 120))  # Cooldown after posting a sale
REGULAR_CHECK_INTERVAL = 300  # Regular check interval (5 minutes)

# Setup storage for keeping track of processed sales
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PROCESSED_SALES_FILE = DATA_DIR / "processed_sales.json"

# Initialize empty list of processed sales if file doesn't exist
if not PROCESSED_SALES_FILE.exists():
    with open(PROCESSED_SALES_FILE, "w") as f:
        json.dump([], f)

def load_processed_sales():
    """Load the list of already processed sale event IDs."""
    with open(PROCESSED_SALES_FILE, "r") as f:
        return json.load(f)

def save_processed_sales(processed_sales):
    """Save the updated list of processed sale event IDs."""
    with open(PROCESSED_SALES_FILE, "w") as f:
        json.dump(processed_sales, f)

def get_eth_price():
    """Get the current price of ETH in USD."""
    # Try multiple price APIs for redundancy
    apis = [
        "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
        "https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD"
    ]
    
    for api_url in apis:
        try:
            print(f"Trying to fetch ETH price from {api_url}")
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different API response formats
                if "ethereum" in data:
                    price = data["ethereum"]["usd"]
                elif "USD" in data:
                    price = data["USD"]
                else:
                    continue
                    
                print(f"Successfully fetched ETH price: ${price}")
                return price
        except Exception as e:
            print(f"Error fetching ETH price from {api_url}: {e}")
            continue
    
    # If all APIs fail, use a fallback price
    # This prevents showing $??? in tweets
    fallback_price = 1825.00  # Set a reasonable fallback price
    print(f"Using fallback ETH price: ${fallback_price}")
    return fallback_price

def fetch_recent_sales(include_bids=True, max_age_days=7):
    """Fetch recent sales from Reservoir API for the specified contract.
    
    Args:
        include_bids (bool): Whether to include bid/offer acceptances as sales
        max_age_days (int): Maximum age of sales to fetch in days
    
    Returns:
        list: List of sales found, or empty list if none
    """
    # Try with a very long time range to ensure we get sales
    from datetime import timedelta
    start_time = int((datetime.now() - timedelta(days=max_age_days)).timestamp())
    
    print(f"Searching for sales of contract {CONTRACT_ADDRESS} on Base chain in the past {max_age_days} days...")
    
    # First try the sales/v6 endpoint with minimal filters
    url = f"{RESERVOIR_BASE_URL}/sales/v6"
    params = {
        "contract": CONTRACT_ADDRESS,
        "limit": 100,  # Increased limit
        "sortDirection": "desc",
        "chains": "base"
    }
    
    sales = fetch_sales_with_params(url, params)
    
    # If we found sales for our contract, return them
    if sales:
        print(f"Found {len(sales)} real sales")
        return sales
    
    print("No regular sales found. Trying a different approach...")
    
    # Try a different endpoint with token activity
    activity_url = f"{RESERVOIR_BASE_URL}/tokens/activity/v5"
    activity_params = {
        "contract": CONTRACT_ADDRESS,
        "limit": 100,
        "types": "sale",
        "sortDirection": "desc",
        "chains": "base"
    }
    
    print(f"Trying token activity endpoint: {activity_url}")
    
    try:
        headers = {
            "Accept": "application/json",
            "x-api-key": RESERVOIR_API_KEY
        }
        
        response = requests.get(activity_url, params=activity_params, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            activities = data.get("activities", [])
            print(f"Found {len(activities)} activities")
            
            if activities:
                # Convert activities to sales format
                converted_sales = []
                for activity in activities:
                    if activity.get("type") == "sale":
                        # Convert to sales format
                        sale = {
                            "id": activity.get("id"),
                            "token": {
                                "tokenId": activity.get("token", {}).get("tokenId"),
                                "contract": activity.get("contract")
                            },
                            "price": activity.get("price"),
                            "orderSide": "ask"  # Default to ask (regular sale)
                        }
                        converted_sales.append(sale)
                
                if converted_sales:
                    print(f"Converted {len(converted_sales)} activities to sales format")
                    return converted_sales
    except Exception as e:
        print(f"Error fetching token activities: {e}")
    
    # If still no sales and include_bids is True, try bid/offer acceptances
    if include_bids:
        # Try to find bid/offer acceptances
        fills_url = f"{RESERVOIR_BASE_URL}/orders/fills/v6"
        print(f"Fetching bid/offer acceptances from {fills_url}")
        
        fills_params = {
            "contract": CONTRACT_ADDRESS,
            "limit": 100,
            "sortDirection": "desc",
            "chains": "base"
        }
        
        try:
            headers = {
                "Accept": "application/json",
                "x-api-key": RESERVOIR_API_KEY
            }
            
            print(f"Fetching bid/offer acceptances from {fills_url}")
            response = requests.get(fills_url, params=fills_params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                fills = data.get("fills", [])
                print(f"Found {len(fills)} bid/offer acceptances")
                
                # Convert order fills to a format similar to sales
                if fills:
                    converted_sales = []
                    for fill in fills:
                        # Only include fills for our contract
                        if fill.get("contract") == CONTRACT_ADDRESS:
                            # Convert to sale format
                            sale = {
                                "id": fill.get("id"),
                                "orderHash": fill.get("orderHash"),
                                "orderSide": "bid",  # This was a bid/offer acceptance
                                "token": {
                                    "contract": fill.get("contract"),
                                    "tokenId": fill.get("tokenId"),
                                    "name": fill.get("tokenName"),
                                    "collection": {
                                        "id": COLLECTION_SLUG,
                                        "name": fill.get("collectionName") or "Primitives"
                                    }
                                },
                                "price": {
                                    "currency": {
                                        "symbol": "ETH"
                                    },
                                    "amount": {
                                        "decimal": float(fill.get("price", 0))
                                    }
                                },
                                "timestamp": int(datetime.fromisoformat(fill.get("createdAt").replace('Z', '+00:00')).timestamp()) if fill.get("createdAt") else int(datetime.now().timestamp())
                            }
                            converted_sales.append(sale)
                    
                    if converted_sales:
                        print(f"Converted {len(converted_sales)} bid/offer acceptances to sales format")
                        return converted_sales
        except Exception as e:
            print(f"Error fetching bid/offer acceptances: {e}")
            import traceback
            traceback.print_exc()
    
    # If we still don't have any sales, log the issue
    print("No sales or bids found for the specified contract address.")
    print("The contract may not have recent sales or the API may not be indexing it correctly.")
    
    # No simulated sales - return empty list
    print("No real sales found. Will check again later.")
    return []

def fetch_sales_with_params(url, params):
    """Helper function to fetch sales with given parameters."""
    headers = {
        "Accept": "application/json",
        "x-api-key": RESERVOIR_API_KEY
    }
    
    print("\n=== Reservoir API Request Details ===")
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    print(f"Headers: {{'Accept': 'application/json', 'x-api-key': '[Hidden for security]'}}")
    
    try:
        print("Making API request...")
        response = requests.get(url, params=params, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
            print(f"Response Preview: {str(data)[:300]}...")
            sales = data.get("sales", [])
            print(f"Found {len(sales)} sales")
            return sales
        else:
            print(f"Error Response: {response.text}")
            print("\nAPI Key Issue: Your Reservoir API key may not be valid or have the necessary permissions.")
            print("Please check your API key at https://reservoir.tools/")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return []

def download_nft_image(token_id, contract_address):
    """Download the NFT image for the given token ID using Reservoir API."""
    url = f"{RESERVOIR_BASE_URL}/tokens/v6"
    
    params = {
        "tokens": f"{contract_address}:{token_id}",
        "includeAttributes": "false",
        "includeTopBid": "false",
        "chains": "base"
    }
    
    headers = {
        "Accept": "application/json",
        "x-api-key": RESERVOIR_API_KEY
    }
    
    try:
        print(f"Fetching image for token {token_id} on contract {contract_address}")
        response = requests.get(url, params=params, headers=headers)
        print(f"Image fetch status code: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            tokens = token_data.get("tokens", [])
            
            if tokens and len(tokens) > 0:
                image_url = tokens[0].get("token", {}).get("image")
                print(f"Found image URL: {image_url}")
                
                if image_url:
                    # Download the image
                    print(f"Downloading image from {image_url}")
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        image_path = DATA_DIR / f"nft_{token_id}.jpg"
                        with open(image_path, "wb") as f:
                            f.write(image_response.content)
                        print(f"Image saved to {image_path}")
                        return str(image_path)
                    else:
                        print(f"Failed to download image: {image_response.status_code}")
                else:
                    print("No image URL found in token data")
            else:
                print("No tokens found in response")
        else:
            print(f"Error fetching token data: {response.status_code} - {response.text}")
        
        # If we get here, we couldn't get the image, so try a direct OpenSea URL as fallback
        try:
            # Construct OpenSea API URL for the asset
            opensea_image_url = f"https://api.opensea.io/api/v2/chain/base/contract/{contract_address}/nfts/{token_id}"
            print(f"Trying OpenSea API fallback: {opensea_image_url}")
            
            # Try to get the image URL from OpenSea
            headers = {"Accept": "application/json"}
            opensea_response = requests.get(opensea_image_url, headers=headers)
            
            if opensea_response.status_code == 200:
                nft_data = opensea_response.json()
                image_url = nft_data.get("nft", {}).get("image_url")
                
                if image_url:
                    # Download the image
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        image_path = DATA_DIR / f"nft_{token_id}.jpg"
                        with open(image_path, "wb") as f:
                            f.write(image_response.content)
                        print(f"Image saved from OpenSea to {image_path}")
                        return str(image_path)
        except Exception as opensea_error:
            print(f"OpenSea fallback failed: {opensea_error}")
        
        return None
    except Exception as e:
        print(f"Exception when downloading NFT image: {e}")
        import traceback
        traceback.print_exc()
        return None

def post_to_twitter(message, image_path=None):
    """Post a tweet with the sale information and optionally an image using Twitter API v2."""
    try:
        # Set up Twitter client with v2 API
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        
        # For media upload, we still need v1.1 API
        if image_path and os.path.exists(image_path):
            print(f"Attempting to upload image: {image_path}")
            # Create v1.1 API instance for media upload
            auth = tweepy.OAuth1UserHandler(
                TWITTER_API_KEY, 
                TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, 
                TWITTER_ACCESS_TOKEN_SECRET
            )
            api_v1 = tweepy.API(auth)
            
            try:
                # Upload media
                media = api_v1.media_upload(image_path)
                # Post tweet with media
                response = client.create_tweet(text=message, media_ids=[media.media_id])
            except Exception as media_error:
                print(f"Error uploading media: {media_error}")
                print("Attempting to post tweet without media...")
                response = client.create_tweet(text=message)
        else:
            # Post tweet without media
            response = client.create_tweet(text=message)
        
        print(f"Successfully posted to Twitter with ID: {response.data['id']}")
        print(f"Tweet content: {message}")
        return True
    except Exception as e:
        print(f"Error posting to Twitter: {e}")
        import traceback
        traceback.print_exc()
        return False

def format_sale_message(sale):
    """Format the sale message according to the specified format."""
    try:
        # Add debugging to understand the sale data structure
        print("Sale data structure:")
        print(json.dumps(sale, indent=2)[:500])  # Print first 500 chars of formatted JSON
        
        # Extract sale information from Reservoir API response
        token_id = sale.get("token", {}).get("tokenId")
        contract = sale.get("token", {}).get("contract")
        
        # Determine if this is a bid/offer acceptance
        is_bid = sale.get("orderSide") == "bid"
        
        # Verify we're using the correct contract
        if contract and contract.lower() != CONTRACT_ADDRESS.lower():
            print(f"Warning: Sale is for contract {contract}, not our target {CONTRACT_ADDRESS}")
            print("Skipping this sale as it's for a different contract")
            return None
        
        # Try to get a more user-friendly token ID or name
        token_name = sale.get("token", {}).get("name")
        collection_name = sale.get("token", {}).get("collection", {}).get("name")
        
        # Handle token ID formatting
        display_id = token_id
        if token_id:
            # If it's a numeric ID, keep it simple
            try:
                # Try to convert to integer if possible
                int_token_id = int(token_id)
                display_id = str(int_token_id)  # This removes leading zeros
                print(f"Using numeric token ID: {display_id}")
            except (ValueError, TypeError):
                # If it's not a simple number or is very long
                if len(str(token_id)) > 10:
                    # If we have a token name, use that instead
                    if token_name:
                        # Extract just the number part if it follows a pattern like "Primitives #123"
                        import re
                        number_match = re.search(r'#(\d+)', token_name)
                        if number_match:
                            display_id = number_match.group(1)
                            print(f"Extracted ID from name: {display_id}")
                        else:
                            display_id = token_name
                            print(f"Using token name as ID: {display_id}")
                    else:
                        # Try to shorten very long IDs
                        try:
                            display_id = f"{token_id[:4]}...{token_id[-4:]}" if len(token_id) > 8 else token_id
                            print(f"Shortened token ID: {display_id}")
                        except:
                            display_id = token_id
                            print(f"Using original token ID: {display_id}")
        
        # Get price information from Reservoir format
        price_data = sale.get("price", {})
        eth_amount = float(price_data.get("amount", {}).get("decimal", 0))
        
        # Get current ETH price
        eth_price = get_eth_price()
        if eth_price:
            usd_amount = eth_amount * eth_price
            usd_formatted = f"${usd_amount:,.2f}"
        else:
            usd_formatted = "$???"
        
        # Determine collection name for the message
        nft_collection = collection_name if collection_name else "Primitive"
        
        # Determine action verb based on whether it's a bid/offer acceptance
        action_verb = "offer accepted for" if sale.get("orderSide") == "bid" else "bought for"
        
        # Format the message
        message = f"{nft_collection} #{display_id} {action_verb} {eth_amount:.4f} Ξ [{usd_formatted}]\n\n⤷https://opensea.io/assets/base/{contract}/{token_id}"
        
        print(f"Formatted message: {message}")
        return message
    except Exception as e:
        print(f"Error formatting sale message: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_new_sales():
    """Check for new sales and process them.
    
    Returns:
        int: Number of sales processed in this check
    """
    # Load list of already processed sales
    processed_sales = load_processed_sales()
    
    # Fetch recent sales including bids/offers
    recent_sales = fetch_recent_sales(include_bids=True)
    
    if not recent_sales:
        print("No sales found in this check. Will try again after cooldown.")
        return 0
    
    # Process new sales
    sales_processed = 0
    for sale in recent_sales:
        # Use order hash as a unique identifier for the sale
        sale_id = sale.get("orderHash", "")
        
        # Skip if this sale has already been processed
        if sale_id in processed_sales:
            continue
        
        print(f"Processing new sale: {sale_id}")
        
        # Get token information
        token_id = sale.get("token", {}).get("tokenId")
        contract_address = sale.get("token", {}).get("contract")
        
        # Skip if not our target contract
        if contract_address and contract_address.lower() != CONTRACT_ADDRESS.lower():
            print(f"Skipping sale for contract {contract_address} (not our target contract)")
            continue
        
        # Format sale message
        message = format_sale_message(sale)
        if not message:
            continue
        
        # Download NFT image
        image_path = download_nft_image(token_id, contract_address)
        
        # Post to Twitter
        success = post_to_twitter(message, image_path)
        
        if success:
            # Add to processed sales list
            processed_sales.append(sale_id)
            save_processed_sales(processed_sales)
            sales_processed += 1
            print(f"Successfully posted sale {sale_id} to Twitter!")
    
    print(f"Processed {sales_processed} new sales in this check")
    return sales_processed

def test_post_last_sale():
    """Test function to fetch and post the last sale, regardless of how long ago it happened."""
    print("Testing: Fetching last sale and posting to Twitter...")
    
    # Keep trying to fetch sales until we find one, with increasing time windows
    max_attempts = 3  # For testing, limit attempts
    attempt = 0
    
    # Try with increasingly longer time periods
    time_periods = [365, 730, 1095]  # 1 year, 2 years, 3 years
    
    while attempt < max_attempts:
        attempt += 1
        days = time_periods[attempt-1]
        print(f"Attempt {attempt} of {max_attempts} to find sales (looking back {days} days)")
        
        # Fetch sales from a longer time period, including bids/offers
        recent_sales = fetch_recent_sales(include_bids=True, max_age_days=days)
        
        if recent_sales:
            print(f"Found {len(recent_sales)} sales to test with")
            
            # Try each sale until we find one that works
            for sale_index, sale in enumerate(recent_sales):
                print(f"\nTrying sale {sale_index + 1} of {len(recent_sales)}")
                
                # Get token information
                token_id = sale.get("token", {}).get("tokenId")
                contract_address = sale.get("token", {}).get("contract")
                
                # Verify we're using the correct contract
                if contract_address and contract_address.lower() != CONTRACT_ADDRESS.lower():
                    print(f"Skipping sale for contract {contract_address} (not our target contract {CONTRACT_ADDRESS})")
                    continue
                
                # Format sale message
                message = format_sale_message(sale)
                if not message:
                    print("Error formatting sale message, trying next sale")
                    continue
                
                # Download NFT image
                print(f"Attempting to download image for token {token_id} on contract {contract_address}")
                image_path = download_nft_image(token_id, contract_address)
                
                # Post to Twitter
                success = post_to_twitter(message, image_path)
                
                if success:
                    print("Test successful: Posted sale to Twitter")
                    if image_path:
                        print(f"Posted with image: {image_path}")
                    else:
                        print("Posted without image")
                    return True
                else:
                    print("Failed to post to Twitter, trying next sale if available")
            
            print("Tried all available sales but none could be posted successfully")
            return False
        else:
            print("No sales found in this attempt")
            
            if attempt < max_attempts:
                wait_time = 10  # For testing, wait 10 seconds instead of 2 minutes
                print(f"Waiting {wait_time} seconds before trying again...")
                time.sleep(wait_time)
    
    print(f"No sales found after {max_attempts} attempts")
    return False

def main():
    """Main function to run the sales bot."""
    print("Starting NFT Sales Bot...")
    print(f"Checking for new sales every {REGULAR_CHECK_INTERVAL} seconds (5 minutes)")
    print(f"After posting a sale, will cool down for {CHECK_INTERVAL} seconds (2 minutes)")
    
    while True:
        # Check for new sales
        print(f"\nChecking for new sales at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sales_found = process_new_sales()
        
        # If sales were found and posted, cool down for a shorter time
        if sales_found > 0:
            print(f"Sales were posted! Cooling down for {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
        else:
            # No sales found, wait for the regular check interval
            print(f"No sales found. Next check in {REGULAR_CHECK_INTERVAL} seconds...")
            time.sleep(REGULAR_CHECK_INTERVAL)

if __name__ == "__main__":
    # If TEST argument is provided, run the test function
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        test_post_last_sale()
    else:
        main()
