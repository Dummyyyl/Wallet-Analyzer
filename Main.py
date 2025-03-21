import os
import random
import time
import re
import tls_client
import cloudscraper
import requests  # Added for Discord webhook
from fake_useragent import UserAgent
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# PRESET YOUR DISCORD WEBHOOK HERE
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1347199891058851994/aBGf72w6EeVzXzYIuMdFSqf4oevsOYu4XVBmaObtYo7asV1WXOTLBzT6qzlc3Bef1xk5"

#####################################
# NEW FUNCTIONS FROM CODE 2 (RPC):  #
#####################################

def get_sol_balance_rpc(wallet_address, rpc_url="https://solana-rpc.publicnode.com"):
    """
    Uses the Solana RPC node to get the SOL balance of the given wallet.
    The RPC endpoint has a rate limit of 1,200 requests per 60 seconds.
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [wallet_address]
    }
    
    response = requests.post(rpc_url, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        balance = result.get("result", {}).get("value", 0)
        return balance / 1_000_000_000  # Convert lamports to SOL
    else:
        raise Exception(f"Error fetching balance: {response.text}")

def check_rpc_balance(wallet):
    """
    Wrapper that returns the SOL balance from the RPC node for the given wallet.
    Returns the balance (in SOL) or None if an error occurs.
    """
    rpc_url = "https://solana-rpc.publicnode.com"
    try:
        return get_sol_balance_rpc(wallet, rpc_url)
    except Exception as e:
        print(f"{Fore.YELLOW}RPC Error for wallet {wallet}: {e}{Style.RESET_ALL}")
        return None

#####################################
# END NEW FUNCTIONS (RPC)           #
#####################################

class WalletChecker:
    def __init__(self):
        self.cloudScraper = cloudscraper.create_scraper()
        self.ua = UserAgent(os='linux', browsers=['firefox'])
    
    def get_headers(self):
        return {
            'Host': 'gmgn.ai',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'dnt': '1',
            'referer': 'https://gmgn.ai/?chain=sol',
            'user-agent': self.ua.random
        }

    def get_wallet_data(self, wallet, period):
        url = f"https://gmgn.ai/defi/quotation/v1/smartmoney/sol/walletNew/{wallet}?period={period}"
        max_retries = 3
        
        # Try using tls_client with random client
        for _ in range(max_retries):
            try:
                client_id = random.choice(['chrome_103', 'safari_15_3', 'firefox_102'])
                session = tls_client.Session(client_identifier=client_id)
                headers = self.get_headers()
                response = session.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('msg') == 'success':
                        return data.get('data')
            except Exception:
                time.sleep(1)
        
        # Fallback to cloudscraper
        for _ in range(max_retries):
            try:
                headers = self.get_headers()
                response = self.cloudScraper.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('msg') == 'success':
                        return data.get('data')
            except Exception:
                time.sleep(1)
        
        return None

    def get_30d_metrics(self, wallet):
        """Get 30-day winrate, all-time ROI, and SOL balance (returns None for missing values)"""
        data = self.get_wallet_data(wallet, '30d')
        
        if not data:
            return None, None, None
        
        # Handle possible None values for each metric
        winrate_value = data.get('winrate')
        winrate = winrate_value * 100 if winrate_value is not None else None
        
        roi_value = data.get('total_profit_pnl')  # All-time ROI
        roi = roi_value * 100 if roi_value is not None else None
        
        sol_balance_value = data.get('sol_balance')
        sol_balance = None
        if sol_balance_value is not None:
            try:
                sol_balance = float(sol_balance_value)
            except (TypeError, ValueError):
                sol_balance = None
        
        return winrate, roi, sol_balance

def process_wallets():
    print("Starting wallet processing...")
    start_time = time.time()
    wallets_checked = 0
    qualified_wallets = 0
    disqualified_wallets = 0

    checker = WalletChecker()
    
    # Read wallets from NewWallets.txt
    with open('NewWallets.txt', 'r') as f:
        wallets = [line.strip() for line in f.readlines() if line.strip()]
    
    # Load already checked wallets if any
    checked = set()
    if os.path.exists('CheckedWallets.txt'):
        with open('CheckedWallets.txt', 'r') as f:
            checked = {line.strip() for line in f.readlines() if line.strip()}
    
    # === PREFILTER: Run through all wallets once using the RPC node to check SOL balance ===
    print(f"\n=== PREFILTERING WALLETS BY RPC SOL BALANCE ===")
    prefiltered_wallets = []
    for wallet in wallets:
        # Skip already checked wallets
        if wallet in checked:
            continue

        print(f"\nPrefiltering {wallet}")
        rpc_sol_balance = check_rpc_balance(wallet)
        if rpc_sol_balance is None:
            print(f"{Fore.YELLOW}Failed to get RPC SOL balance for {wallet}, skipping.{Style.RESET_ALL}")
            disqualified_wallets += 1
            # Mark as checked so we don't process it later
            with open('CheckedWallets.txt', 'a') as f:
                f.write(f"{wallet}\n")
            continue
        
        if rpc_sol_balance < 0.5:
            print(f"{Fore.RED}Wallet SOL balance ({rpc_sol_balance:.2f}) is below threshold (0.5 SOL) via RPC. Skipping wallet.{Style.RESET_ALL}")
            disqualified_wallets += 1
            with open('CheckedWallets.txt', 'a') as f:
                f.write(f"{wallet}\n")
        else:
            print(f"{Fore.GREEN}Wallet {wallet} passed prefilter (RPC balance: {rpc_sol_balance:.2f} SOL).{Style.RESET_ALL}")
            prefiltered_wallets.append(wallet)
    
    # Update NewWallets.txt with only the prefiltered wallets
    with open('NewWallets.txt', 'w') as f:
        if prefiltered_wallets:
            f.write('\n'.join(prefiltered_wallets) + '\n')
        else:
            f.write('')

    # === END PREFILTERING ===
    print(f"\nPrefiltering complete. {len(prefiltered_wallets)} wallets passed the RPC SOL balance check.")

    # Now process each prefiltered wallet with the GMGN part
    for wallet in prefiltered_wallets.copy():
        wallets_checked += 1
        print(f"\nProcessing {wallet} with GMGN...")
        winrate, roi, sol_balance = checker.get_30d_metrics(wallet)
        
        # Mark wallet as checked regardless of result
        with open('CheckedWallets.txt', 'a') as f:
            f.write(f"{wallet}\n")
        prefiltered_wallets.remove(wallet)
        with open('NewWallets.txt', 'w') as f:
            if prefiltered_wallets:
                f.write('\n'.join(prefiltered_wallets) + '\n')
            else:
                f.write('')
        
        # Check for incomplete data; count as disqualified if incomplete
        if any(metric is None for metric in [winrate, roi, sol_balance]):
            print(f"{Fore.YELLOW}Failed to get complete data from GMGN for {wallet}{Style.RESET_ALL}")
            disqualified_wallets += 1
            continue
            
        # Criteria check
        winrate_ok = winrate > 75
        roi_ok = roi >= 50  # All-time ROI criteria
        sol_ok = sol_balance >= 0.5
        
        status = [
            f"Winrate (30d): {winrate:.1f}% {'✅' if winrate_ok else '❌'}",
            f"ROI (All-time): {roi:.1f}% {'✅' if roi_ok else '❌'}",
            f"SOL Balance (GMGN): {sol_balance:.2f} {'✅' if sol_ok else '❌'}"
        ]
        
        print(" | ".join(status))
        
        if all([winrate_ok, roi_ok, sol_ok]):
            with open('GoodWallets.txt', 'a') as f:
                f.write(f"{wallet}\n")
            print(f"{Fore.GREEN}🔥 QUALIFIED WALLET!{Style.RESET_ALL}")
            qualified_wallets += 1
        else:
            print(f"{Fore.RED}⛔ Doesn't meet all criteria for {wallet}{Style.RESET_ALL}")
            disqualified_wallets += 1
        
        time.sleep(1)  # Rate limiting

    end_time = time.time()
    duration_seconds = end_time - start_time
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{minutes} minutes {seconds} seconds"
    start_time_str = time.strftime("%d.%m.%Y - %H:%M", time.localtime(start_time))
    
    metrics = {
        "wallets_checked": wallets_checked,
        "qualified_wallets": qualified_wallets,
        "disqualified_wallets": disqualified_wallets,
        "start_time": start_time_str,
        "duration": duration_str,
    }
    
    return metrics

def send_to_discord(metrics):
    """Send GoodWallets.txt to Discord and clear the file along with processing metrics"""
    if not os.path.exists('GoodWallets.txt'):
        print(f"{Fore.YELLOW}No good wallets to send{Style.RESET_ALL}")
        return

    try:
        with open('GoodWallets.txt', 'rb') as f:
            files = {'file': ('GoodWallets.txt', f)}
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            # Message now includes actual values from metrics
            message = (
                "```\n"
                "📊 WALLET PROCESSING SUMMARY\n"
                "-----------------------------\n"
                f"📅 Start Time: {metrics['start_time']}\n"
                f"⏳ Duration: {metrics['duration']}\n"
                f"🔥 Qualified Wallets: {metrics['qualified_wallets']}\n"
                f"⛔ Disqualified Wallets: {metrics['disqualified_wallets']}\n"
                "```"
                )
            
            response = requests.post(
                DISCORD_WEBHOOK,
                data={'content': message},
                files=files
            )
            
        if response.status_code == 200:
            print(f"{Fore.GREEN}Successfully sent to Discord{Style.RESET_ALL}")
            # Clear the file after successful send
            open('GoodWallets.txt', 'w').close()
        else:
            print(f"{Fore.RED}Failed to send to Discord: {response.status_code}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error sending to Discord: {str(e)}{Style.RESET_ALL}")

def show_menu():
    """Display the main menu and get user choice"""
    print(f"\n{Fore.CYAN}Main Menu:{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}1. Start wallet processing")
    print("2. Clean duplicates")
    print("3. Format wallets")
    print(f"4. Exit{Style.RESET_ALL}")
    
    while True:
        choice = input("Enter your choice (1-4): ")
        if choice in ['1', '2', '3', '4']:
            return int(choice)
        print(f"{Fore.RED}Invalid input! Please enter 1, 2, 3, or 4.{Style.RESET_ALL}")

def deduplicate_checked_wallets():
    """Remove duplicates from CheckedWallets.txt"""
    if not os.path.exists('CheckedWallets.txt'):
        return 0
    
    # Read existing checked wallets
    with open('CheckedWallets.txt', 'r') as f:
        wallets_before = [line.strip() for line in f.readlines() if line.strip()]
    
    # Get unique wallets
    unique_wallets = list(set(wallets_before))
    
    # Write back unique wallets
    with open('CheckedWallets.txt', 'w') as f:
        f.write('\n'.join(unique_wallets) + '\n')
    
    # Calculate actual duplicates removed
    duplicates_removed = len(wallets_before) - len(unique_wallets)
    return duplicates_removed

def clean_new_wallets():
    """Remove wallets from NewWallets.txt that exist in CheckedWallets.txt"""
    # Read checked wallets first
    checked_wallets = set()
    if os.path.exists('CheckedWallets.txt'):
        with open('CheckedWallets.txt', 'r') as f:
            checked_wallets = {line.strip() for line in f.readlines() if line.strip()}
    
    # Process NewWallets.txt
    if not os.path.exists('NewWallets.txt'):
        return 0
    
    with open('NewWallets.txt', 'r') as f:
        new_wallets = [line.strip() for line in f.readlines() if line.strip()]
    
    original_count = len(new_wallets)
    cleaned = [w for w in new_wallets if w not in checked_wallets]
    
    with open('NewWallets.txt', 'w') as f:
        f.write('\n'.join(cleaned) + '\n')
    
    return original_count - len(cleaned)

def process_duplicates():
    """Handle duplicate cleaning operations"""
    print("\nCleaning duplicates...")
    
    # Deduplicate CheckedWallets
    checked_count = deduplicate_checked_wallets()
    print(f"Removed duplicates from CheckedWallets: {checked_count}")
    
    # Clean NewWallets
    new_count = clean_new_wallets()
    print(f"Removed duplicates from NewWallets: {new_count}")
    
    input("\nPress Enter to return to menu...")

def format_wallets():
    """Extract wallet addresses from formatted NewWallets.txt"""
    if not os.path.exists('NewWallets.txt'):
        print(f"{Fore.RED}NewWallets.txt not found!{Style.RESET_ALL}")
        return 0

    # Regex pattern to extract wallet addresses from URLs
    pattern = re.compile(r'wallet_address_tb0534=([A-Za-z0-9]{32,44})')

    with open('NewWallets.txt', 'r') as f:
        lines = [line.strip() for line in f.readlines()]

    cleaned = []
    for line in lines:
        match = pattern.search(line)
        if match:
            cleaned.append(match.group(1))
        else:
            print(f"{Fore.YELLOW}Skipped invalid entry: {line}{Style.RESET_ALL}")

    # Write cleaned wallets back
    with open('NewWallets.txt', 'w') as f:
        f.write('\n'.join(cleaned) + '\n')

    return len(cleaned)

def main():
    while True:
        choice = show_menu()
        
        if choice == 1:
            # Prompt to send results to Discord after processing
            should_send_discord = input("\nDo you want to send the results to Discord after processing? (y/n): ").strip().lower() == 'y'
            
            metrics = process_wallets()
            
            if should_send_discord:
                send_to_discord(metrics)
            
            input("\nPress Enter to return to the menu...")
        elif choice == 2:
            process_duplicates()
        elif choice == 3:
            print(f"\n{Fore.GREEN}Formatting wallets...{Style.RESET_ALL}")
            count = format_wallets()
            print(f"Successfully formatted {count} wallet entries")
            input("\nPress Enter to return to the menu...")
        elif choice == 4:
            print(f"\n{Fore.GREEN}Exiting program...{Style.RESET_ALL}")
            break

if __name__ == "__main__":
    main()
