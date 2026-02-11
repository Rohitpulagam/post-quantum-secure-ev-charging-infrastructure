import base64
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("crypto")

try:
    import oqs  # type: ignore
    OQS_AVAILABLE = True
except Exception:
    OQS_AVAILABLE = False

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


@dataclass
class CryptoConfig:
    mode: str  # 'PQC' or 'ECC'
    sign_algo: Optional[str] = None  # e.g., 'Dilithium2' or 'Falcon-512' for PQC; 'Ed25519' for ECC
    kem_algo: Optional[str] = None   # e.g., 'Kyber512' or None


class CryptoSuite:
    def __init__(self, cfg: CryptoConfig):
        self.cfg = cfg
        self._pvt = None
        self._pub = None
        self._oqs_sign: Optional["oqs.Signature"] = None

    def generate(self):
        # Check if mode indicates PQC usage (handles 'PQC', 'PQC_ONLY', 'HYBRID')
        use_pqc = self.cfg.mode and ('PQC' in self.cfg.mode.upper() or self.cfg.mode.upper() == 'HYBRID')
        
        if use_pqc and OQS_AVAILABLE and self.cfg.sign_algo:
            logger.info("Using PQC signature algorithm: %s", self.cfg.sign_algo)
            self._oqs_sign = oqs.Signature(self.cfg.sign_algo)
            # liboqs-python: generate_keypair returns the public key; secret key kept internally
            pk = self._oqs_sign.generate_keypair()
            self._pvt = None
            self._pub = pk
        else:
            # ECC fallback via Ed25519
            logger.info("Using ECC fallback signature: Ed25519")
            self.cfg.mode = 'ECC'
            self.cfg.sign_algo = 'Ed25519'
            key = Ed25519PrivateKey.generate()
            self._pvt = key
            self._pub = key.public_key()

    def public_key_bytes(self) -> bytes:
        use_pqc = self.cfg.mode and ('PQC' in self.cfg.mode.upper() or self.cfg.mode.upper() == 'HYBRID')
        
        if use_pqc and self._oqs_sign is not None and isinstance(self._pub, (bytes, bytearray)):
            return bytes(self._pub)
        elif self.cfg.mode == 'ECC' and isinstance(self._pub, Ed25519PublicKey):
            return self._pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        raise RuntimeError("Keys not generated or invalid state")

    def sign(self, data: bytes) -> bytes:
        use_pqc = self.cfg.mode and ('PQC' in self.cfg.mode.upper() or self.cfg.mode.upper() == 'HYBRID')
        
        if use_pqc and self._oqs_sign is not None:
            return self._oqs_sign.sign(data)
        elif self.cfg.mode == 'ECC' and isinstance(self._pvt, Ed25519PrivateKey):
            return self._pvt.sign(data)
        raise RuntimeError("Private key not available for signing")

    def verify(self, data: bytes, sig: bytes, pubkey: Optional[bytes] = None) -> bool:
        try:
            use_pqc = self.cfg.mode and ('PQC' in self.cfg.mode.upper() or self.cfg.mode.upper() == 'HYBRID')
            
            if use_pqc and self._oqs_sign is not None:
                pk = pubkey if pubkey is not None else self.public_key_bytes()
                return self._oqs_sign.verify(data, sig, pk)
            elif self.cfg.mode == 'ECC':
                if pubkey is None:
                    pk_obj = self._pub
                else:
                    pk_obj = Ed25519PublicKey.from_public_bytes(pubkey)
                assert isinstance(pk_obj, Ed25519PublicKey)
                pk_obj.verify(sig, data)
                return True
        except Exception as e:
            logger.warning("Signature verify failed: %s", e)
            return False
        return False

    def export_public_key_b64(self) -> str:
        return base64.b64encode(self.public_key_bytes()).decode('ascii')

    @staticmethod
    def choose_algorithms(pqc_supported: bool) -> CryptoConfig:
        if pqc_supported and OQS_AVAILABLE:
            # Prefer Dilithium2 then Falcon-512
            try_algos = ["Dilithium2", "Falcon-512"]
            for alg in try_algos:
                if alg in oqs.get_enabled_sig_mechanisms():
                    # Kyber check for KEM
                    kem = None
                    try_kem = ["Kyber512", "Kyber768", "Kyber1024"]
                    for k in try_kem:
                        if k in oqs.get_enabled_kem_mechanisms():
                            kem = k
                            break
                    return CryptoConfig(mode='PQC', sign_algo=alg, kem_algo=kem)
        # Fallback to ECC
        return CryptoConfig(mode='ECC', sign_algo='Ed25519', kem_algo=None)
