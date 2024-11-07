from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
from stellar_sdk.exceptions import BadResponseError
from hashlib import sha256
import requests

# Initialize keypairs
USDC_ISSUER = Keypair.from_raw_ed25519_seed(sha256(b"usdcissuer").digest())
ADMIN_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"admin").digest())
MM_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"marketmaker").digest())

CHARITY_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"charitywallet").digest())
GIFTCARD_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"giftcardwallet").digest())

# Define USDC asset
USDC = Asset("USDC", USDC_ISSUER.public_key)

# Connect to testnet
server = Server("https://horizon-testnet.stellar.org")
network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE

def setup_accounts():
    """Create and fund accounts on testnet"""
    print("Funding accounts from friendbot...")
    #USDC_ISSUER, ADMIN_KEYPAIR, MM_KEYPAIR]
    print(CHARITY_KEYPAIR, GIFTCARD_KEYPAIR)
    for kp in [CHARITY_KEYPAIR, GIFTCARD_KEYPAIR]:
        try:
            url = f"https://friendbot.stellar.org?addr={kp.public_key}"
            response = requests.get(url)
            response.raise_for_status()
            print(f"Funded {kp.public_key[:8]}...")
        except Exception as e:
            print(f"Error funding {kp.public_key[:8]}: {str(e)}")

def create_and_distribute_usdc():
    """Create USDC asset and distribute to admin and market maker"""
    try:
        # Build transaction for creating trustlines ADMIN_KEYPAIR, MM_KEYPAIR
        for recipient in [CHARITY_KEYPAIR, GIFTCARD_KEYPAIR]:
            account = server.load_account(recipient.public_key)
            transaction = (
                TransactionBuilder(
                    source_account=account,
                    network_passphrase=network_passphrase,
                    base_fee=100)
                .append_change_trust_op(asset=USDC)
                .set_timeout(30)
                .build()
            )
            transaction.sign(recipient)
            server.submit_transaction(transaction)
            print(f"Created trustline for {recipient.public_key[:8]}")

        # # Issue USDC
        # issuer_account = server.load_account(USDC_ISSUER.public_key)
        # total_supply = "1000000000"  # 1 billion
        # distribution_amount = str(int(total_supply) // 2)  # 50%

        # # Send to admin
        # transaction = (
        #     TransactionBuilder(
        #         source_account=issuer_account,
        #         network_passphrase=network_passphrase,
        #         base_fee=100)
        #     .append_payment_op(
        #         destination=ADMIN_KEYPAIR.public_key,
        #         asset=USDC,
        #         amount=distribution_amount
        #     )
        #     .set_timeout(30)
        #     .build()
        # )
        # transaction.sign(USDC_ISSUER)
        # server.submit_transaction(transaction)
        # print(f"Sent {distribution_amount} USDC to admin")

        # # Send to market maker
        # issuer_account = server.load_account(USDC_ISSUER.public_key)
        # transaction = (
        #     TransactionBuilder(
        #         source_account=issuer_account,
        #         network_passphrase=network_passphrase,
        #         base_fee=100)
        #     .append_payment_op(
        #         destination=MM_KEYPAIR.public_key,
        #         asset=USDC,
        #         amount=distribution_amount
        #     )
        #     .set_timeout(30)
        #     .build()
        # )
        # transaction.sign(USDC_ISSUER)
        # server.submit_transaction(transaction)
        # print(f"Sent {distribution_amount} USDC to market maker")

    except BadResponseError as e:
        print(f"Error: {e.message}")

def create_market_order():
    """Create 1:1 USDC/XLM sell order"""
    try:
        mm_account = server.load_account(MM_KEYPAIR.public_key)
        transaction = (
            TransactionBuilder(
                source_account=mm_account,
                network_passphrase=network_passphrase,
                base_fee=100)
            .append_manage_sell_offer_op(
                selling=USDC,
                buying=Asset.native(),
                amount="100000",  # Start with 100k USDC order
                price="1",  # 1:1 ratio
            )
            .set_timeout(30)
            .build()
        )
        transaction.sign(MM_KEYPAIR)
        server.submit_transaction(transaction)
        print("Created 1:1 USDC/XLM sell order")

    except BadResponseError as e:
        print(f"Error: {e.message}")

def main():
    print("Setting up USDC on Stellar testnet...")
    #setup_accounts()
    create_and_distribute_usdc()
    #create_market_order()
    print("Setup complete!")

if __name__ == "__main__":
    main()