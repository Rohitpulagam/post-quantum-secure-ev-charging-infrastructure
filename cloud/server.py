import asyncio
import base64
import json
import logging
from typing import Dict, Any, Optional
import websockets

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
from ev_station.crypto import CryptoSuite, CryptoConfig

# Try to import oqs for PQC
try:
    import oqs
    OQS_AVAILABLE = True
except ImportError:
    OQS_AVAILABLE = False

logger = logging.getLogger("cloud")


class CloudServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._server: Optional[websockets.server.Serve] = None
        self._stations: Dict[str, Dict[str, Any]] = {}

    async def run(self):
        """Start the cloud backend server"""
        async with websockets.serve(self._handle_station, self.host, self.port):
            logger.info("Cloud backend listening on %s:%d", self.host, self.port)
            await asyncio.Future()  # run forever

    async def _handle_station(self, ws: websockets.WebSocketServerProtocol):
        peer = ws.remote_address
        logger.info("Station connected via WS from %s", peer)
        
        station_id = f"station_{peer[0]}_{peer[1]}"
        self._stations[station_id] = {"ws": ws, "peer": peer}
        
        try:
            async for data in ws:
                obj = json.loads(data)
                await self._process_message(obj, ws, station_id)
        except Exception as e:
            logger.error("Cloud station WS session error: %s", e)
        finally:
            logger.info("Station WS connection closed")

    async def _process_message(self, msg: Dict[str, Any], ws: websockets.WebSocketServerProtocol, station_id: str):
        action = msg.get("ocpp_action") or msg.get("action")
        payload = msg.get("payload", {})
        
        if action == "BootNotification":
            sid = payload.get("station_id")
            self._stations[sid] = {
                "pubkey_b64": payload.get("pubkey_b64"),
                "algo": payload.get("algo"),
                "mode": payload.get("mode"),
            }
            logger.info("BootNotification from %s (algo=%s mode=%s)", sid, payload.get("algo"), payload.get("mode"))
            await self._send(ws, {"ocpp_action": "BootNotificationRes", "payload": {"status": "Accepted"}})
        
        elif action == "VerifyVehicleCert":
            # Cloud verifies vehicle certificate using PQC signature
            vehicle_pubkey_b64 = payload.get("vehicle_pubkey_b64")
            vehicle_signature_b64 = payload.get("vehicle_signature_b64")
            challenge_data_b64 = payload.get("challenge_data_b64")
            vehicle_algo = payload.get("algo") or payload.get("vehicle_algo")  # Accept both field names
            vehicle_mode = payload.get("mode") or payload.get("vehicle_mode") or "PQC"
            
            logger.info("Cloud verifying vehicle certificate (algo: %s)", vehicle_algo)
            
            # Decode data
            vehicle_pubkey = base64.b64decode(vehicle_pubkey_b64)
            vehicle_signature = base64.b64decode(vehicle_signature_b64)
            challenge_data = base64.b64decode(challenge_data_b64)
            
            # Create crypto suite for verification
            verify_crypto = CryptoSuite(CryptoConfig(
                mode=vehicle_mode,
                sign_algo=vehicle_algo,
                kem_algo=None
            ))
            verify_crypto.generate()  # Initialize OQS if needed
            
            # Verify signature
            try:
                is_valid = verify_crypto.verify(challenge_data, vehicle_signature, vehicle_pubkey)
                logger.info("Vehicle certificate verification: %s", "SUCCESS" if is_valid else "FAILED")
                
                await self._send(ws, {
                    "action": "VerifyVehicleCertRes",
                    "payload": {
                        "ok": is_valid,
                        "reason": "Signature valid" if is_valid else "Signature invalid"
                    }
                })
            except Exception as e:
                logger.error("Certificate verification error: %s", e)
                await self._send(ws, {
                    "action": "VerifyVehicleCertRes",
                    "payload": {
                        "ok": False,
                        "reason": f"Verification error: {e}"
                    }
                })
        
        elif action == "AuthorizeCert":
            # Stub verification of certificate authenticity
            veh_cert = payload.get("vehicle_cert", {})
            ok = veh_cert.get("issuer") == "MockCPO"
            logger.info("AuthorizeCert: issuer=%s ok=%s", veh_cert.get("issuer"), ok)
            await self._send(ws, {"ocpp_action": "AuthorizeCertRes", "payload": {"ok": ok}})
        
        elif action == "Authorize":
            logger.info("Authorize: %s", payload)
            await self._send(ws, {"ocpp_action": "AuthorizeRes", "payload": {"status": "Accepted"}})
        elif action == "MeterValues":
            station_id = payload.get("station_id")
            station = self._stations.get(station_id, {})
            sig_b64 = payload.get("sig_b64")
            reading = payload.get("reading")
            algo = payload.get("algo")
            mode = payload.get("mode")
            pub_b64 = payload.get("pubkey_b64") or station.get("pubkey_b64")
            data = json.dumps(reading, sort_keys=True).encode("utf-8")
            signature = base64.b64decode(sig_b64)
            pub = base64.b64decode(pub_b64) if pub_b64 else b""
            verified = False
            try:
                if mode == 'ECC' or algo == 'Ed25519':
                    Ed25519PublicKey.from_public_bytes(pub).verify(signature, data)
                    verified = True
                else:
                    # For PQC, attempt to use oqs if available
                    try:
                        import oqs  # type: ignore
                        with oqs.Signature(algo) as sig:
                            verified = sig.verify(data, signature, pub)
                    except Exception as e:
                        logger.warning("PQC verify unavailable or failed: %s", e)
                        verified = False
            except Exception as e:
                logger.warning("ECC verify failed: %s", e)
                verified = False
            logger.info("MeterValues: signature verified=%s", verified)
            await self._send(ws, {"ocpp_action": "MeterValuesRes", "payload": {"verified": verified}})
        elif action == "StopTransaction":
            logger.info("StopTransaction: %s", payload)
            await self._send(ws, {"ocpp_action": "StopTransactionRes", "payload": {"status": "Accepted"}})
        else:
            logger.warning("Unknown action: %s", action)
            await self._send(ws, {"ocpp_action": "Error", "payload": {"error": "Unknown action"}})

    async def _send(self, ws: websockets.WebSocketServerProtocol, obj: Dict[str, Any]):
        await ws.send(json.dumps(obj))

    async def run(self):
        """Start the cloud backend server"""
        async with websockets.serve(self._handle_station, self.host, self.port):
            logger.info("Cloud backend listening on %s:%d", self.host, self.port)
            await asyncio.Future()  # run forever


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )
    
    server = CloudServer(host="0.0.0.0", port=9000)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Cloud server stopped")
