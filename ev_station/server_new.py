import asyncio
import base64
import json
import logging
import ssl
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from xml.etree import ElementTree as ET
from pathlib import Path

from .v2gtp import send_xml, read_xml, V2GTP_XML_PAYLOAD
from .crypto import CryptoSuite, CryptoConfig
import websockets

# OQS availability check
try:
    import oqs
    OQS_AVAILABLE = True
except ImportError:
    OQS_AVAILABLE = False

logger = logging.getLogger("station")

# SUPPORTED MODES
# Time Complexity: O(1)
# ============================================================
SUPPORTED_MODES = ["PQC_ONLY", "HYBRID", "CLASSICAL_FALLBACK"]
DEFAULT_MODE = "HYBRID"

# STATION CONFIGURATION
# Time Complexity: O(1)
# ============================================================
@dataclass
class StationConfig:
    bind_host: str
    bind_port: int
    cloud_host: str
    cloud_port: int
    use_pqc_tls: bool = False
    pqc_mode: str = DEFAULT_MODE
    use_pqc_tls: bool = False  # Enable PQC certificates


class StationServer:
    """
    CHARGING STATION (SECC)

    ISO-15118 inspired server with PQC.
    Measures time taken per protocol phase.

    Overall Session Time Complexity: O(1)
    """

    def __init__(self, bind_host, bind_port, cloud_host, cloud_port, use_pqc_tls=False):
        self.cfg = StationConfig(bind_host, bind_port, cloud_host, cloud_port, use_pqc_tls=use_pqc_tls)
        self._server: Optional[asyncio.AbstractServer] = None
        self._cloud_ws: Optional[websockets.WebSocketClientProtocol] = None
        self._crypto: Optional[CryptoSuite] = None
        self._ev_pubkey: Optional[bytes] = None
        self._ssl_ctx: Optional[ssl.SSLContext] = None
        self._negotiated_algo: Optional[str] = None

    # CONNECT TO CLOUD
    # Time Complexity: O(1)
    # ============================================================
    async def _connect_cloud_ws(self):
        """Connect to cloud backend via WebSocket."""
        try:
            self._cloud_ws = await websockets.connect(
                f"ws://{self.cfg.cloud_host}:{self.cfg.cloud_port}",
                ping_interval=20,
                ping_timeout=10
            )
            logger.info("Connected to cloud at %s:%d", 
                        self.cfg.cloud_host, self.cfg.cloud_port)
        except Exception as e:
            logger.warning("Failed to connect to cloud: %s", e)
            self._cloud_ws = None
            raise

    async def _verify_vehicle_cert_with_cloud(self, cert_req_elem) -> bool:
        """Forward vehicle certificate to cloud for verification"""
        if not self._cloud_ws:
            logger.warning("No cloud connection, skipping vehicle cert verification")
            return True  # Fallback to local trust if cloud unavailable
        
        try:
            # Extract vehicle certificate data from CertificateExchangeReq
            vehicle_pubkey_b64 = cert_req_elem.findtext("pubkey_b64") or ""
            vehicle_signature_b64 = cert_req_elem.findtext("signature_b64") or ""
            challenge_data_b64 = cert_req_elem.findtext("challenge_b64") or ""
            
            
            # Send to cloud for verification
            verify_msg = {
                "action": "VerifyVehicleCert",
                "payload": {
                    "vehicle_pubkey_b64": vehicle_pubkey_b64,
                    "vehicle_signature_b64": vehicle_signature_b64,
                    "challenge_data_b64": challenge_data_b64,
                    "algo": self._negotiated_algo or "Falcon-512"  # Use negotiated algorithm
                }
            }
            
            logger.info("Sending to cloud: algo=%s, negotiated_algo=%s", 
                       verify_msg["payload"]["algo"], self._negotiated_algo)
            await self._cloud_ws.send(json.dumps(verify_msg))
            logger.info("Sent vehicle certificate to cloud for verification")
            
            # Wait for cloud response
            response = await asyncio.wait_for(self._cloud_ws.recv(), timeout=5.0)
            resp_msg = json.loads(response)
            
            if resp_msg.get("action") == "VerifyVehicleCertRes":
                ok = resp_msg["payload"].get("ok", False)
                reason = resp_msg["payload"].get("reason", "")
                logger.info("Cloud verification result: ok=%s reason=%s", ok, reason)
                return ok
            
            logger.warning("Unexpected cloud response: %s", resp_msg.get("action"))
            return False
            
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for cloud certificate verification")
            return False
        except Exception as e:
            logger.error("Error during cloud certificate verification: %s", e)
            return False

    # STOP SERVER
    # Time Complexity: O(1)
    # ============================================================
    async def stop(self):
        """Stop the station server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Station server stopped")
        
        if self._cloud_ws:
            await self._cloud_ws.close()
            self._cloud_ws = None
            logger.info("Cloud WebSocket closed")

    # START SERVER
    # Time Complexity: O(1)
    # ============================================================
    async def start(self):

        try:
            await self._connect_cloud_ws()
        except Exception as e:
            logger.warning(
                "Cloud WS not available, running local-only mode: %s", e
            )

        # Initialize PQC crypto (station generates its own keys)
        self._crypto = CryptoSuite(CryptoSuite.choose_algorithms(pqc_supported=True))
        self._crypto.generate()

        self._ssl_ctx = self._build_server_ssl_context()

        self._server = await asyncio.start_server(
            self._handle_client,
            self.cfg.bind_host,
            self.cfg.bind_port,
            ssl=self._ssl_ctx
        )

        logger.info(
            "Station listening on %s:%d",
            self.cfg.bind_host,
            self.cfg.bind_port
        )

        async with self._server:
            await self._server.serve_forever()

    # HANDLE EV CONNECTION
    # Time Complexity per session: O(1)
    # ============================================================
    async def _handle_client(self, reader, writer):

        session_start = time.perf_counter()

        peer = writer.get_extra_info("peername")
        logger.info("EV connected from %s", peer)
        
        # Log TLS connection info
        ssl_object = writer.get_extra_info("ssl_object")
        if ssl_object:
            logger.info("TLS handshake successful: version=%s, cipher=%s",
                        ssl_object.version(), ssl_object.cipher())
        else:
            logger.warning("No TLS detected for connection from %s", peer)

        try:
            await self._session_handler(reader, writer)
        except ssl.SSLError as e:
            logger.error("TLS handshake/protocol error from %s: %s", peer, e)
        except asyncio.IncompleteReadError as e:
            logger.error("Incomplete read from %s (expected %d, got %d bytes): %s", 
                         peer, e.expected, len(e.partial), e)
        except ConnectionResetError as e:
            logger.warning("Connection reset by peer %s: %s", peer, e)
        except ValueError as e:
            logger.error("Protocol error from %s: %s", peer, e)
        except Exception as e:
            logger.error("Unexpected session error from %s: %s", peer, e, exc_info=True)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass  # Ignore close errors

            session_end = time.perf_counter()
            logger.info(
                "TOTAL EV SESSION TIME (SERVER): %.2f ms",
                (session_end - session_start) * 1000
            )
            logger.info("EV session %s closed", peer)

    # ISO-15118 FSM (SERVER SIDE)
    # ============================================================
    async def _session_handler(self, reader, writer):

        # PHASE 1 — Protocol Negotiation
        # Steps 1–2
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        _, elem = await read_xml(reader)
        if elem.tag != "SessionSetupReq":
            raise ValueError("Expected SessionSetupReq")

        res = ET.Element("SessionSetupRes")
        supported = ET.SubElement(res, "supported")
        for m in SUPPORTED_MODES:
            ET.SubElement(supported, "mode").text = m
        ET.SubElement(res, "selected_mode").text = self.cfg.pqc_mode
        await send_xml(writer, res, V2GTP_XML_PAYLOAD)

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 1 (Protocol Negotiation) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # PHASE 2 — Algorithm Negotiation
        # Steps 3–5
        # Time Complexity: O(n)
        # ======================================================
        phase_start = time.perf_counter()

        _, elem = await read_xml(reader)
        if elem.tag != "AlgorithmNegReq":
            raise ValueError("Expected AlgorithmNegReq")

        ev_sig_prefs = [e.text for e in elem.findall("sig_prefs/alg")]
        ev_kem_prefs = [e.text for e in elem.findall("kem_prefs/alg")]

        if not OQS_AVAILABLE:
            # Fall back to ECC when OQS is not available
            logger.warning("PQC algorithms requested but oqs not available, falling back to ECC")
            chosen_sig = "Ed25519"
            chosen_kem = None
            mode = "ECC"
        else:
            enabled_sigs = set(oqs.get_enabled_sig_mechanisms())
            enabled_kems = set(oqs.get_enabled_kem_mechanisms())

            # Find first matching algorithm from EV preferences
            chosen_sig = next((s for s in ev_sig_prefs if s in enabled_sigs), None)
            if not chosen_sig:
                # Fallback to preferred algorithms
                preferred_fallbacks = ["Dilithium2", "Falcon-512", "Dilithium3"]
                chosen_sig = next((s for s in preferred_fallbacks if s in enabled_sigs), None)
                if not chosen_sig and enabled_sigs:
                    chosen_sig = sorted(enabled_sigs)[0]  # Pick any available
                if not chosen_sig:
                    # Ultimate fallback to ECC
                    logger.warning("No PQC signature algorithms available, falling back to ECC")
                    chosen_sig = "Ed25519"
                    chosen_kem = None
                    mode = "ECC"
            
            if chosen_sig != "Ed25519":
                chosen_kem = next((k for k in ev_kem_prefs if k in enabled_kems), None)
                if not chosen_kem:
                    preferred_kem_fallbacks = ["Kyber512", "Kyber768", "Kyber1024"]
                    chosen_kem = next((k for k in preferred_kem_fallbacks if k in enabled_kems), None)
                    if not chosen_kem and enabled_kems:
                        chosen_kem = sorted(enabled_kems)[0]
                    if not chosen_kem:
                        logger.warning("No PQC KEM algorithms available")
                        chosen_kem = None
                mode = "PQC_ONLY"
            
        logger.info("Negotiated algorithms: sig=%s kem=%s mode=%s", chosen_sig, chosen_kem, mode if 'mode' in locals() else "PQC_ONLY")

        # Save negotiated algorithm for later use
        self._negotiated_algo = chosen_sig

        # Regenerate crypto with negotiated algorithms
        self._crypto = CryptoSuite(
            CryptoConfig(
                mode=mode if 'mode' in locals() else "PQC_ONLY",
                sign_algo=chosen_sig,
                kem_algo=chosen_kem
            )
        )
        self._crypto.generate()

        res = ET.Element("AlgorithmNegRes")
        ET.SubElement(res, "sign_algo").text = chosen_sig
        ET.SubElement(res, "kem_algo").text = chosen_kem or ""
        ET.SubElement(res, "mode").text = mode if 'mode' in locals() else "PQC_ONLY"
        await send_xml(writer, res, V2GTP_XML_PAYLOAD)

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 2 (Algorithm Negotiation) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # PHASE 3 — Certificate Exchange
        # Steps 6–8
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        _, elem = await read_xml(reader)
        if elem.tag != "CertificateExchangeReq":
            raise ValueError("Expected CertificateExchangeReq")

        self._ev_pubkey = base64.b64decode(elem.findtext("pubkey_b64") or "")

        res = ET.Element("CertificateExchangeRes")
        ET.SubElement(res, "pubkey_b64").text = self._crypto.export_public_key_b64()
        await send_xml(writer, res, V2GTP_XML_PAYLOAD)

        # Send vehicle certificate to cloud for verification
        verification_ok = await self._verify_vehicle_cert_with_cloud(elem)
        
        res = ET.Element("CertVerifyRes")
        ET.SubElement(res, "ok").text = str(verification_ok)
        if not verification_ok:
            ET.SubElement(res, "reason").text = "Cloud verification failed"
        await send_xml(writer, res, V2GTP_XML_PAYLOAD)

        if not verification_ok:
            logger.warning("Vehicle certificate verification failed, closing connection")
            return

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 3 (Certificate Exchange) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # PHASE 4 — Authorization
        # Steps 9–12
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        _, elem = await read_xml(reader)
        if elem.tag != "AuthorizationReq":
            raise ValueError("Expected AuthorizationReq")

        payload = {
            "contract_id": elem.findtext("payload/contract_id"),
            "timestamp": float(elem.findtext("payload/timestamp") or "0"),
        }
        sig = base64.b64decode(elem.findtext("sig_b64") or "")
        data = json.dumps(payload, sort_keys=True).encode()

        ok = self._crypto.verify(data, sig, self._ev_pubkey)

        res = ET.Element("AuthorizationRes")
        ET.SubElement(res, "authorized").text = "True" if ok else "False"
        await send_xml(writer, res, V2GTP_XML_PAYLOAD)

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 4 (Authorization) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

        # PHASE 5 — Charging + Stop
        # Steps 13–16
        # Time Complexity: O(1)
        # ======================================================
        phase_start = time.perf_counter()

        await send_xml(writer, ET.Element("StartCharging"), V2GTP_XML_PAYLOAD)

        _, elem = await read_xml(reader)
        if elem.tag != "StopReq":
            raise ValueError("Expected StopReq")

        await send_xml(writer, ET.Element("StopRes"), V2GTP_XML_PAYLOAD)

        phase_end = time.perf_counter()
        logger.info(
            "PHASE 5 (Charging + Stop) took %.2f ms",
            (phase_end - phase_start) * 1000
        )

    # TLS CONTEXT BUILDER
    # Time Complexity: O(1)
    # ============================================================
    async def _run_openssl_server(self):
        """Run OpenSSL s_server with OQS provider for PQC TLS"""
        base = Path(__file__).resolve().parents[1]
        cert_path = base / "certs_pqc/secc_cert.pem"
        key_path = base / "certs_pqc/secc_key.pem"
        ca_path = base / "certs_pqc/ca_cert.pem"
        
        logger.info("Starting OpenSSL s_server with PQC certificates")
        logger.info("Cert: %s", cert_path)
        logger.info("Key: %s", key_path)
        logger.info("CA: %s", ca_path)
        
        cmd = [
            "openssl", "s_server",
            "-cert", str(cert_path),
            "-key", str(key_path),
            "-CAfile", str(ca_path),
            "-accept", str(self.cfg.bind_port),
            "-verify_return_error",
            "-Verify", "1",
            "-tls1_3",
            "-provider", "oqsprovider",
            "-provider", "default",
            "-msg",  # Show protocol messages
        ]
        
        logger.info("Command: %s", " ".join(cmd))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        logger.info("OpenSSL s_server started (PID: %s)", process.pid)
        logger.info("Station ready and listening with PQC TLS...")
        
        # Monitor stderr for connection logs
        async def log_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.info("OpenSSL: %s", line.decode().strip())
        
        stderr_task = asyncio.create_task(log_stderr())
        
        try:
            await process.wait()
        finally:
            stderr_task.cancel()
            logger.info("OpenSSL s_server stopped")
    
    def _build_server_ssl_context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        base = Path(__file__).resolve().parents[1]
        
        # Use PQC certificates if enabled and available
        if self.cfg.use_pqc_tls and (base / "certs_pqc").exists():
            cert_path = base / "certs_pqc/secc_cert.pem"
            key_path = base / "certs_pqc/secc_key.pem"
            ca_path = base / "certs_pqc/ca_cert.pem"
            logger.info("Using PQC certificates (ML-DSA)")
        else:
            cert_path = base / "certs/secc_cert.pem"
            key_path = base / "certs/secc_key.pem"
            ca_path = base / "certs/ca.pem"
            logger.info("Using classical certificates (ECDSA)")
        
        logger.info("Server cert: %s (exists: %s)", cert_path, cert_path.exists())
        logger.info("Server key: %s (exists: %s)", key_path, key_path.exists())
        logger.info("CA cert: %s (exists: %s)", ca_path, ca_path.exists())
        
        # Try to load certificates - if PQC fails, fall back to classical
        try:
            ctx.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path)
            )
            ctx.load_verify_locations(str(ca_path))
        except ssl.SSLError as e:
            if self.cfg.use_pqc_tls and "key too small" in str(e).lower():
                logger.warning("Python ssl module cannot load PQC certificates: %s", e)
                logger.warning("Falling back to classical certificates")
                logger.warning("Note: For true PQC support, use openssl s_server directly or hybrid certificates")
                # Fall back to classical certificates
                cert_path = base / "certs/secc_cert.pem"
                key_path = base / "certs/secc_key.pem"
                ca_path = base / "certs/ca.pem"
                ctx.load_cert_chain(
                    certfile=str(cert_path),
                    keyfile=str(key_path)
                )
                ctx.load_verify_locations(str(ca_path))
            else:
                raise
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.check_hostname = False
        
        # Set minimum TLS version for security and compatibility
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        
        logger.info("Server TLS context configured: protocol=%s, verify_mode=%s",
                    ctx.protocol, ctx.verify_mode)
        return ctx


# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    cfg = StationConfig(
        bind_host="0.0.0.0",
        bind_port=9000,
        cloud_host="127.0.0.1",
        cloud_port=9001
    )
    server = StationServer(
        cfg.bind_host,
        cfg.bind_port,
        cfg.cloud_host,
        cfg.cloud_port
    )
    asyncio.run(server.start())

