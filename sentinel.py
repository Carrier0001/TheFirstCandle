import json
import hashlib
import datetime
import sqlite3
import requests
import random
import os
from pathlib import Path
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

class Mirror:
    def __init__(self):
        self.db_path = "mirror.db"
        self.canary_db_path = "canary_alerts.db"
        self.init_db()
        self.init_canary_db()
        
        # GeoIP cache
        self.geo_cache = {}
        
        # Canary tokens (decoy credentials)
        self.canary_tokens = {
            "aws_key": "AKIA-VOW-LEDGER-PROD-2026",
            "aws_secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "db_user": "admin",
            "db_password": "VowLedger_Prod_2026!",
            "api_key": "sk-live-vow-mirror-prod-7f3a8b2c",
            "ssh_key_fingerprint": "SHA256:VOWLEDGERPROD2026MIRROR",
            "jwt_secret": "vow-mirror-prod-jwt-secret-change-me"
        }
        
        # Fake agency names for psychological effect
        self.agencies = [
            "ECHELON - Signals Intelligence Division",
            "SENTINEL - Threat Analysis Unit",
            "OASIS - Dark Web Monitoring",
            "GHOST - Counter-Intelligence"
        ]

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS probes (
                timestamp TEXT,
                fingerprint_hash TEXT PRIMARY KEY,
                ip TEXT,
                asn TEXT,
                country TEXT,
                city TEXT,
                path TEXT,
                method TEXT,
                user_agent TEXT,
                tor BOOLEAN,
                severity INTEGER,
                agency_assigned TEXT,
                notes TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ip ON probes(ip)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_severity ON probes(severity)')
        conn.commit()
        conn.close()

    def init_canary_db(self):
        conn = sqlite3.connect(self.canary_db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS canary_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                token_type TEXT,
                token_value TEXT,
                ip TEXT,
                user_agent TEXT,
                request_data TEXT,
                severity INTEGER DEFAULT 5,
                notified BOOLEAN DEFAULT FALSE
            )
        ''')
        conn.commit()
        conn.close()

    def enrich_fingerprint(self, request: Request):
        ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
        ua = request.headers.get("user-agent", "unknown")
        method = request.method
        path = str(request.url.path)
        
        fp_hash = hashlib.sha256(f"{ip}{ua}{path}{datetime.datetime.utcnow().isoformat()}".encode()).hexdigest()[:64]
        
        # Get geo with caching
        geo = self._get_geo_cached(ip)
        
        # Assign random agency (for psychological effect)
        agency = random.choice(self.agencies)
        
        return {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "ip": ip,
            "fingerprint_hash": fp_hash,
            "path": path,
            "method": method,
            "user_agent": ua,
            "country": geo.get("country"),
            "city": geo.get("city"),
            "asn": geo.get("asn"),
            "tor": self._check_tor(ip),
            "severity": 1,
            "agency_assigned": agency
        }

    def _get_geo_cached(self, ip: str):
        if ip in self.geo_cache:
            return self.geo_cache[ip]
        
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,city,as,asname,isp,org", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    result = {
                        "country": data.get('country'),
                        "city": data.get('city'),
                        "asn": data.get('as'),
                        "asname": data.get('asname'),
                        "isp": data.get('isp'),
                        "org": data.get('org')
                    }
                    self.geo_cache[ip] = result
                    return result
        except:
            pass
        
        return {"country": "Unknown", "city": "Unknown", "asn": "Unknown"}

    def _check_tor(self, ip):
        try:
            # Cache Tor list for 1 hour
            if not hasattr(self, '_tor_cache') or (datetime.datetime.now() - self._tor_cache_time).seconds > 3600:
                r = requests.get("https://check.torproject.org/torbulkexitlist", timeout=5)
                self._tor_cache = set(r.text.splitlines()) if r.status_code == 200 else set()
                self._tor_cache_time = datetime.datetime.now()
            return ip in self._tor_cache
        except:
            return False

    def log_probe(self, fp):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT OR REPLACE INTO probes 
            (timestamp, fingerprint_hash, ip, asn, country, city, path, method, user_agent, tor, severity, agency_assigned, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fp["timestamp"], fp["fingerprint_hash"], fp["ip"], fp.get("asn"),
            fp.get("country"), fp.get("city"), fp["path"], fp["method"],
            fp["user_agent"], fp["tor"], fp["severity"], fp["agency_assigned"],
            "Automated reconnaissance probe"
        ))
        conn.commit()
        conn.close()

    def check_canary_token(self, request: Request, body: dict = None) -> bool:
        """Check if request contains any canary tokens"""
        # Check headers
        headers_str = str(dict(request.headers))
        # Check query params
        query_str = str(request.query_params)
        # Check body
        body_str = str(body) if body else ""
        
        all_data = f"{headers_str}{query_str}{body_str}".lower()
        
        for token_name, token_value in self.canary_tokens.items():
            if token_value.lower() in all_data:
                self.log_canary_hit(request, token_name, token_value)
                return True
        return False

    def log_canary_hit(self, request: Request, token_type: str, token_value: str):
        """Log canary token usage (high severity)"""
        conn = sqlite3.connect(self.canary_db_path)
        ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
        
        conn.execute('''
            INSERT INTO canary_hits (timestamp, token_type, token_value, ip, user_agent, request_data, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.datetime.utcnow().isoformat() + "Z",
            token_type,
            token_value[:50],
            ip,
            request.headers.get("user-agent", "unknown"),
            json.dumps({
                "headers": dict(request.headers),
                "query": dict(request.query_params),
                "method": request.method,
                "path": request.url.path
            }),
            5
        ))
        conn.commit()
        conn.close()
        
        # Also log as high severity probe
        fp = self.enrich_fingerprint(request)
        fp["severity"] = 5
        fp["notes"] = f"CANARY_TOKEN_TRIGGERED: {token_type}"
        self.log_probe(fp)

    async def respond(self, request: Request):
        fp = self.enrich_fingerprint(request)
        
        # Check for canary tokens in request
        if self.check_canary_token(request):
            return await self._canary_alert_response(fp)
        
        # Check for sensitive paths
        sensitive_paths = [".env", "admin", "key", "secret", ".git", "config", "wp-config", "backup", "aws", "credential"]
        is_sensitive = any(x in request.url.path.lower() for x in sensitive_paths)
        
        if is_sensitive:
            fp["severity"] = 3
            self.log_probe(fp)
            return await self._sensitive_response(fp)
        
        # Standard probe
        self.log_probe(fp)
        return await self._standard_response(fp)

    async def _standard_response(self, fp):
        return JSONResponse({
            "status": "forbidden",
            "reference": fp["fingerprint_hash"][:32],
            "message": "Activity logged.",
            "timestamp": fp["timestamp"]
        }, status_code=403)

    async def _sensitive_response(self, fp):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ACCESS LOGGED</title>
            <style>
                body {{ background:#0a0a0a; color:#aaaaaa; font-family:'Courier New', monospace; padding:50px; }}
                .header {{ color:#ff5555; border-bottom:1px solid #333; padding-bottom:10px; }}
                .detail {{ color:#888; margin:20px 0; }}
                hr {{ border-color:#222; margin:30px 0; }}
                .warning {{ color:#ff8888; }}
            </style>
        </head>
        <body>
            <div style="max-width:700px; margin:auto;">
                <div class="header">⚡ VOW LEDGER — MIRROR DEFENSE SYSTEM ⚡</div>
                
                <h2>Reconnaissance Activity Logged</h2>
                
                <p><strong>Reference:</strong> VLM-2026-{fp['fingerprint_hash'][:12]}</p>
                <p><strong>Timestamp:</strong> {fp['timestamp']}</p>
                <p><strong>Origin:</strong> {fp.get('country', 'Unknown')} • {fp.get('city', 'Unknown')}</p>
                <p><strong>ASN:</strong> {fp.get('asn', 'Unknown')}</p>
                <p><strong>Target:</strong> {fp['path']}</p>
                <p><strong>Tor Exit Node:</strong> {'Yes' if fp['tor'] else 'No'}</p>
                <p><strong>Assigned To:</strong> {fp['agency_assigned']}</p>
                
                <hr>
                
                <div class="warning">
                    <p>⚠️ This probe has been permanently recorded.</p>
                    <p>⚠️ Your fingerprint has been added to the threat intelligence database.</p>
                    <p>⚠️ Repeated hostile reconnaissance will be published to the public ledger.</p>
                </div>
                
                <div class="detail">
                    <p style="font-size:0.9em;">🔒 This system deploys canary tokens. Attempting to use any discovered credentials will trigger immediate escalation.</p>
                </div>
                
                <hr>
                
                <p style="color:#666; font-size:0.85em;">
                    The Vow Ledger is immutable.<br>
                    This record cannot be deleted or modified.<br>
                    No further correspondence will be entered into.
                </p>
                
                <p style="color:#444; margin-top:40px; font-size:0.8em;">
                    Mirror Division — Permanent Records<br>
                    Case ID: {fp['fingerprint_hash'][:16]}
                </p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html, status_code=403)

    async def _canary_alert_response(self, fp):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>⚠️ CREDENTIAL COMPROMISE DETECTED</title>
            <style>
                body {{ background:#0a0a0a; color:#ff4444; font-family:'Courier New', monospace; padding:50px; }}
                .critical {{ color:#ff0000; font-size:1.2em; border:2px solid #ff0000; padding:20px; background:#1a0000; }}
                .blink {{ animation: blink 1s step-start infinite; }}
                @keyframes blink {{ 50% {{ opacity: 0; }} }}
                hr {{ border-color:#330000; }}
            </style>
        </head>
        <body>
            <div style="max-width:700px; margin:auto;">
                <div class="critical">
                    <h1 class="blink">⚠️ SECURITY ALERT ⚠️</h1>
                    <h2>Canary Token Triggered</h2>
                </div>
                
                <p><strong>Reference:</strong> 🔴 CANARY-2026-{fp['fingerprint_hash'][:12]}</p>
                <p><strong>Timestamp:</strong> {fp['timestamp']}</p>
                <p><strong>Origin:</strong> {fp.get('country', 'Unknown')} • {fp.get('city', 'Unknown')}</p>
                <p><strong>ASN:</strong> {fp.get('asn', 'Unknown')}</p>
                <p><strong>Tor Exit Node:</strong> {'Yes' if fp['tor'] else 'No'}</p>
                
                <hr>
                
                <div class="critical">
                    <p>🔴 HIGH SEVERITY EVENT — CANARY TOKEN ACTIVATED 🔴</p>
                    <p>This incident has been escalated to maximum severity.</p>
                    <p>All associated credentials have been automatically revoked and traced.</p>
                </div>
                
                <hr>
                
                <p style="color:#ff8888; margin-top:30px;">
                    This event has been logged with HIGH severity.<br>
                    Your activity is now under active review.<br>
                    The Vow Ledger does not forget. The Mirror does not forgive.
                </p>
                
                <p style="color:#666; margin-top:40px; font-size:0.85em;">
                    Severity: CRITICAL (Level 5)<br>
                    Retention: Indefinite<br>
                    No appeals. No redactions.
                </p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html, status_code=403)

    def get_stats(self):
        """Get statistics about probes and canary hits"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT COUNT(*) FROM probes')
        total_probes = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(DISTINCT ip) FROM probes')
        unique_ips = cursor.fetchone()[0]
        conn.close()
        
        conn = sqlite3.connect(self.canary_db_path)
        cursor = conn.execute('SELECT COUNT(*) FROM canary_hits')
        canary_hits = cursor.fetchone()[0] if conn else 0
        conn.close()
        
        return {
            "total_probes": total_probes,
            "unique_attackers": unique_ips,
            "canary_triggers": canary_hits,
            "status": "active"
        }

# Global instance
mirror = Mirror()
