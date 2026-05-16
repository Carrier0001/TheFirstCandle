# app/p2p/api.py - Replace FastAPI with libp2p

from libp2p import new_node
from libp2p.peer import PeerInfo
import asyncio
import json

class P2PLedgerNode:
    """
    Every instance is a peer, no central server
    Uses libp2p (same as IPFS, Filecoin)
    """
    
    def __init__(self):
        self.node = None
        self.streams = []
    
    async def start(self, listen_port=4001):
        # Start libp2p node
        self.node = await new_node(
            transport_opt=["tcp"],
            listen_opt=[f"/ip4/0.0.0.0/tcp/{listen_port}"],
            muxer_opt="mplex",
            security_opt="secio"
        )
        
        # Set up handlers
        self.node.set_stream_handler("/vow/submit", self.handle_submit)
        self.node.set_stream_handler("/vow/sync", self.handle_sync)
        self.node.set_stream_handler("/vow/jury/vote", self.handle_jury_vote)
        
        # Bootstrap to network
        await self.bootstrap_to_peers()
        
        print(f"✅ P2P node started: {self.node.get_id().pretty()}")
    
    async def handle_submit(self, stream):
        """Receive submission from another peer"""
        data = await stream.read()
        submission = json.loads(data)
        
        # Store locally
        result = await distributed_ledger.submit_entry(submission)
        
        # Broadcast to other peers
        await self.broadcast_to_peers("/vow/submit", data)
        
        # Send receipt back
        await stream.write(json.dumps(result).encode())
        await stream.close()
    
    async def broadcast_to_peers(self, protocol, data):
        """Gossip protocol - send to random subset of peers"""
        peers = self.node.get_peerstore().get_peers()
        
        # Send to 5 random peers
        for peer in random.sample(peers, min(5, len(peers))):
            try:
                stream = await self.node.new_stream(peer, [protocol])
                await stream.write(data)
                await stream.close()
            except:
                pass  # Peer offline, continue
    
    async def sync_from_network(self):
        """Pull latest entries from peers"""
        peers = self.node.get_peerstore().get_peers()
        
        for peer in peers:
            try:
                stream = await self.node.new_stream(peer, ["/vow/sync"])
                await stream.write(json.dumps({"since": self.last_sync}).encode())
                response = await stream.read()
                entries = json.loads(response)
                
                # Merge entries
                for entry in entries:
                    await self.merge_entry(entry)
                    
            except:
                continue
