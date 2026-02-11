import asyncio
import base64
import json
import logging
import ssl
import subprocess
import sys
from pathlib import Path
import time
from typing import List, Optional, Tuple
from xml.etree import ElementTree as ET

# Import shared V2GTP helpers
from ev_station.v2gtp import send_xml, read_xml, V2GTP_XML_PAYLOAD
from ev_station.crypto import CryptoSuite, CryptoConfig

logger = logging.getLogger("vehicle")


class VehicleClient:
    """
    ELECTRIC VEHICLE (EVCC)

    Implements ISO-15118-style EV-side protocol with PQC.
    Measures time taken for each protocol phase.

    Overall Time Complexity per session: O(1)
    """

    def __init__(
        self,
        station_host: str,
        station_port: int,
        pqc_modes: Optional[List[str]] = None,
        sig_prefs: Optional[List[str]] = None,
        kem_prefs: Optional[List[str]] = None,
        vehicle_name: Optional[str] = None,
        use_pqc_tls: bool = False,  # Enable PQC certificates
    ):
        """
        Initialize EV client

        Time Complexity: O(1)
        """
        self.station_host = station_host
        self.station_port = station_port
        self.pqc_modes = pqc_modes
        self.sig_prefs = sig_prefs
        self.kem_prefs = kem_prefs
        self.vehicle_name = vehicle_name or "EV-CLIENT"
        self.use_pqc_tls = use_pqc_tls

        # Initial crypto only to advertise preferences
        self._crypto: CryptoSuite = CryptoSuite(
            CryptoSuite.choose_algorithms(pqc_supported=True)
        )
        self._crypto.generate()

        self._ssl_ctx: Optional[ssl.SSLContext] = None

    # ============================================================
    # START EV SESSION
    # Time Complexity: O(1)
    # ============================================================
    async def run_session(self):

        session_start = time.perf_counter()

        logger.info(
            "Connecting to station %s:%d using %s",
            self.station_host,
            self.station_port,
            "PQC-enabled TLS" if self.use_pqc_tls else "classical TLS"
        )

        self._ssl_ctx = self._build_client_ssl_context()

        try:
            reader, writer = await asyncio.open_connection(
                self.station_host,
                self.station_port,
                ssl=self._ssl_ctx,
            )
        except ssl.SSLError as e:
            logger.error("TLS handshake failed with %s:%d", 
                         self.station_host, self.station_port)
            logger.error("SSL Error details: %s", str(e))
            logger.error("This usually means:")
            logger.error("  1. Server is not using TLS (plain TCP)")
            logger.error("  2. Certificate validation failed")
            logger.error("  3. TLS version mismatch")
            logger.error("  4. No server running on port %d", self.station_port)
            raise RuntimeError(f"TLS connection failed: {e}") from e
        except ConnectionRefusedError:
            logger.error("Connection refused to %s:%d - is server running?", 
                         self.station_host, self.station_port)
            raise
        except OSError as e:
            logger.error("Network error connecting to %s:%d: %s", 
                         self.station_host, self.station_port, e)
            raise

        logger.info(
            "Connected to station at %s:%d",
            self.station_host,
            self.station_port,
        )
        
        # Log TLS connection info
        ssl_object = writer.get_extra_info("ssl_object")
        if ssl_object:
            logger.info("TLS handshake successful: version=%s, cipher=%s",
                        ssl_object.version(), ssl_object.cipher())
        else:
            logger.error("No TLS detected - this should not happen!")

        try:
            await self._fsm(reader, writer)
        finally:
            writer.close()
            await writer.wait_closed()

            session_end = time.perf_counter()
            logger.info(
                "TOTAL SESSION TIME: %.2f ms",
                (session_end - session_start) * 1000
            )
            logger.info("EV session closed")

    # ============================================================
    # ISO-15118 FSM (CLIENT SIDE)
    # ============================================================
    async def _fsm(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

        # ======================================================
        #  PHASE 1 — Protocol Negotiation
        # Steps 1–2
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        ev_modes = self.pqc_modes or ["PQC_ONLY", "HYBRID", "CLASSICAL_FALLBACK"]
        req = ET.Element("SessionSetupReq")
        supports = ET.SubElement(req, "supports")
        for m in ev_modes:
            ET.SubElement(supports, "mode").text = m

        await send_xml(writer, req, V2GTP_XML_PAYLOAD)
        _, elem = await read_xml(reader)
        if elem.tag != "SessionSetupRes":
            raise ValueError(f"Expected SessionSetupRes, got {elem.tag}")

        selected_mode = elem.findtext("selected_mode")
        logger.info("Selected PQC mode: %s", selected_mode)

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 1 (Protocol Negotiation) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # ======================================================
        # PHASE 2 — Algorithm Negotiation
        # Steps 3–5
        # Time Complexity: O(n), n = number of algorithms
        # ======================================================
        phase_start = time.perf_counter()

        ev_sig_prefs: List[str] = self.sig_prefs or [
            self._crypto.cfg.sign_algo or "Dilithium2",
            "Falcon-512",
            "Ed25519",
        ]
        ev_kem_prefs: List[str] = self.kem_prefs or [
            self._crypto.cfg.kem_algo or "Kyber512"
        ]

        req = ET.Element("AlgorithmNegReq")
        sig_el = ET.SubElement(req, "sig_prefs")
        for s in ev_sig_prefs:
            ET.SubElement(sig_el, "alg").text = s

        kem_el = ET.SubElement(req, "kem_prefs")
        for k in ev_kem_prefs:
            ET.SubElement(kem_el, "alg").text = k

        await send_xml(writer, req, V2GTP_XML_PAYLOAD)
        _, elem = await read_xml(reader)
        if elem.tag != "AlgorithmNegRes":
            raise ValueError(f"Expected AlgorithmNegRes, got {elem.tag}")

        sign_algo = elem.findtext("sign_algo")
        kem_algo = elem.findtext("kem_algo")
        mode = elem.findtext("mode")

        logger.info(
            "Negotiated algorithms: SIGN=%s KEM=%s MODE=%s",
            sign_algo,
            kem_algo,
            mode,
        )

        self._crypto = CryptoSuite(
            CryptoConfig(mode=mode, sign_algo=sign_algo, kem_algo=kem_algo)
        )
        self._crypto.generate()

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 2 (Algorithm Negotiation) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # ======================================================
        # PHASE 3 — Certificate Exchange
        # Steps 6–8
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        veh_cert = {
            "id": "EV-CERT-123",
            "subject": "EV-001",
            "issuer": "MockCPO",
            "valid_from": int(time.time()) - 1000,
            "valid_to": int(time.time()) + 86400,
        }
        
        # Create challenge data for signature
        challenge_data = f"{veh_cert['subject']}_{time.time()}".encode('utf-8')
        signature = self._crypto.sign(challenge_data)

        req = ET.Element("CertificateExchangeReq")
        cert_el = ET.SubElement(req, "cert")
        for k, v in veh_cert.items():
            ET.SubElement(cert_el, k).text = str(v)

        ET.SubElement(req, "pubkey_b64").text = self._crypto.export_public_key_b64()
        ET.SubElement(req, "signature_b64").text = base64.b64encode(signature).decode('ascii')
        ET.SubElement(req, "challenge_b64").text = base64.b64encode(challenge_data).decode('ascii')
        ET.SubElement(req, "algo").text = sign_algo or "unknown"
        await send_xml(writer, req, V2GTP_XML_PAYLOAD)

        _, elem = await read_xml(reader)
        if elem.tag != "CertificateExchangeRes":
            raise ValueError(f"Expected CertificateExchangeRes, got {elem.tag}")

        _, elem = await read_xml(reader)
        if elem.tag != "CertVerifyRes":
            raise ValueError(f"Expected CertVerifyRes, got {elem.tag}")
        
        cert_ok = elem.findtext("ok") == "True"
        if not cert_ok:
            reason = elem.findtext("reason") or "Unknown"
            logger.error("Certificate verification failed: %s", reason)
            raise RuntimeError(f"Certificate verification failed: {reason}")

        logger.info("Certificate verified by station (via cloud)")

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 3 (Certificate Exchange) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # ======================================================
        # PHASE 4 — Authorization (CRITICAL)
        # Steps 9–12
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        payload = {
            "contract_id": "CONTRACT-ABC-001",
            "timestamp": time.time(),
        }
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = self._crypto.sign(data)

        req = ET.Element("AuthorizationReq")
        payload_el = ET.SubElement(req, "payload")
        ET.SubElement(payload_el, "contract_id").text = payload["contract_id"]
        ET.SubElement(payload_el, "timestamp").text = str(payload["timestamp"])
        ET.SubElement(req, "sig_b64").text = base64.b64encode(sig).decode("ascii")

        await send_xml(writer, req, V2GTP_XML_PAYLOAD)
        _, elem = await read_xml(reader)
        if elem.tag != "AuthorizationRes":
            raise ValueError(f"Expected AuthorizationRes, got {elem.tag}")

        logger.info("Authorization successful")

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 4 (Authorization) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # ======================================================
        # PHASE 5 — Charging & Termination
        # Steps 13–16
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        _, elem = await read_xml(reader)
        if elem.tag != "StartCharging":
            raise ValueError(f"Expected StartCharging, got {elem.tag}")
        logger.info("Charging started")

        await asyncio.sleep(0.5)

        await send_xml(writer, ET.Element("StopReq"), V2GTP_XML_PAYLOAD)
        _, elem = await read_xml(reader)
        if elem.tag != "StopRes":
            raise ValueError(f"Expected StopRes, got {elem.tag}")

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 5 (Charging + Stop) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

    # ============================================================
    # TLS CONTEXT BUILDER
    # Time Complexity: O(1)
    # ============================================================
    async def _connect_openssl_client(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect using OpenSSL s_client with OQS provider"""
        base = Path(__file__).resolve().parents[1]
        cert_path = base / "certs_pqc/evcc_cert.pem"
        key_path = base / "certs_pqc/evcc_key.pem"
        ca_path = base / "certs_pqc/ca_cert.pem"
        
        logger.info("Using OpenSSL s_client with OQS provider")
        logger.info("Cert: %s", cert_path)
        logger.info("Key: %s", key_path)
        logger.info("CA: %s", ca_path)
        
        cmd = [
            "openssl", "s_client",
            "-connect", f"{self.host}:{self.port}",
            "-cert", str(cert_path),
            "-key", str(key_path),
            "-CAfile", str(ca_path),
            "-verify", "1",
            "-tls1_3",
            "-provider", "oqsprovider",
            "-provider", "default",
            "-quiet",  # Suppress info messages
            "-ign_eof",  # Don't close on EOF from stdin
        ]
        
        logger.info("Command: %s", " ".join(cmd))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Wait for connection to establish
        await asyncio.sleep(1)
        
        if process.returncode is not None:
            stderr = await process.stderr.read()
            raise ConnectionError(f"OpenSSL s_client failed: {stderr.decode()}")
        
        logger.info("PQC TLS connection established via OpenSSL (PID: %s)", process.pid)
        
        # Create StreamReader/Writer from subprocess pipes
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        
        # Wrap the process pipes
        class ProcessStreamWriter:
            def __init__(self, process):
                self.process = process
                self._transport = None
            
            def write(self, data):
                self.process.stdin.write(data)
            
            async def drain(self):
                await self.process.stdin.drain()
            
            def close(self):
                self.process.stdin.close()
            
            async def wait_closed(self):
                self.process.terminate()
                await self.process.wait()
        
        # Feed stdout to reader
        async def feed_reader():
            while True:
                data = await process.stdout.read(4096)
                if not data:
                    break
                reader.feed_data(data)
            reader.feed_eof()
        
        asyncio.create_task(feed_reader())
        
        writer = ProcessStreamWriter(process)
        return reader, writer
    
    def _build_client_ssl_context(self):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        base = Path(__file__).resolve().parents[1]

        # Use PQC certificates if enabled and available
        if self.use_pqc_tls and (base / "certs_pqc").exists():
            cert_path = base / "certs_pqc/evcc_cert.pem"
            key_path = base / "certs_pqc/evcc_key.pem"
            ca_path = base / "certs_pqc/ca_cert.pem"
            logger.info("Client using PQC certificates (ML-DSA)")
        else:
            cert_path = base / "certs/evcc_cert.pem"
            key_path = base / "certs/evcc_key.pem"
            ca_path = base / "certs/ca.pem"
            logger.info("Client using classical certificates (ECDSA)")
        
        logger.info("Client cert: %s (exists: %s)", cert_path, cert_path.exists())
        logger.info("Client key: %s (exists: %s)", key_path, key_path.exists())
        logger.info("CA cert: %s (exists: %s)", ca_path, ca_path.exists())

        # Try to load certificates - if PQC fails, fall back to classical
        try:
            ctx.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path),
            )
            ctx.load_verify_locations(str(ca_path))
        except ssl.SSLError as e:
            if self.use_pqc_tls and "key too small" in str(e).lower():
                logger.warning("Python ssl module cannot load PQC certificates: %s", e)
                logger.warning("Falling back to classical certificates")
                logger.warning("Note: For true PQC support, use openssl s_client directly or hybrid certificates")
                # Fall back to classical certificates
                cert_path = base / "certs/evcc_cert.pem"
                key_path = base / "certs/evcc_key.pem"
                ca_path = base / "certs/ca.pem"
                ctx.load_cert_chain(
                    certfile=str(cert_path),
                    keyfile=str(key_path),
                )
                ctx.load_verify_locations(str(ca_path))
            else:
                raise
        # Hostname verification disabled for local testing with self-signed certs
        # SECURITY WARNING: Enable in production with proper CN/SAN matching
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        
        # Set minimum TLS version for security and compatibility
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        
        logger.info("Client TLS context configured: protocol=%s, verify_mode=%s",
                    ctx.protocol, ctx.verify_mode)
        return ctx


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    client = VehicleClient(
        station_host="127.0.0.1",
        station_port=9000,
    )
    asyncio.run(client.run_session())

