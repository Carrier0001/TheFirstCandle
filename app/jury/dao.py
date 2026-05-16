# app/jury/dao.py - Replace central jury with smart contracts

from web3 import Web3
from eth_account import Account
import json

class DAOJury:
    """
    Jury runs on Ethereum (or L2)
    Anyone can stake tokens to become a juror
    Results are on-chain, immutable
    """
    
    def __init__(self):
        # Connect to Ethereum (or Polygon for lower fees)
        self.w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
        
        # Load jury contract
        with open("contracts/JuryDAO.json") as f:
            self.contract = self.w3.eth.contract(
                address=os.getenv("JURY_CONTRACT_ADDRESS"),
                abi=json.load(f)["abi"]
            )
    
    async def submit_for_validation(self, submission_hash: str):
        """Submit entry hash to DAO for validation"""
        
        # Call smart contract
        tx_hash = self.contract.functions.submitEntry(
            submission_hash
        ).transact({
            'from': self.submitter_address,
            'value': Web3.to_wei(0.01, 'ether')  # Small fee to prevent spam
        })
        
        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Get validation period (48 hours typically)
        validation_ends_at = self.contract.functions.getValidationDeadline(
            submission_hash
        ).call()
        
        return {
            "submission_hash": submission_hash,
            "tx_hash": tx_hash.hex(),
            "valid_until": validation_ends_at,
            "check_url": f"https://etherscan.io/tx/{tx_hash.hex()}"
        }
    
    async def get_jury_verdict(self, submission_hash: str):
        """Check if entry was validated"""
        
        verdict = self.contract.functions.getVerdict(submission_hash).call()
        
        if verdict == 1:
            return "APPROVED"
        elif verdict == 2:
            return "REJECTED"
        else:
            return "PENDING"
