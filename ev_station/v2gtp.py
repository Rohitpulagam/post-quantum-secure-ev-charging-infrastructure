import asyncio
import logging
from typing import Tuple
from xml.etree import ElementTree as ET

logger = logging.getLogger("v2gtp")

V2GTP_VERSION = 0x01
V2GTP_XML_PAYLOAD = 0x8001  # simplified: XML payload type


def _inverse_byte(b: int) -> int:
    return b ^ 0xFF


def encode_xml(payload_type: int, elem: ET.Element) -> bytes:
    data = ET.tostring(elem, encoding="utf-8")
    version = V2GTP_VERSION
    inverse = _inverse_byte(version)
    # Frame: version(1), inverse(1), payload_type(2 BE), length(4 BE), payload
    header = bytes([
        version,
        inverse,
        (payload_type >> 8) & 0xFF,
        payload_type & 0xFF,
        (len(data) >> 24) & 0xFF,
        (len(data) >> 16) & 0xFF,
        (len(data) >> 8) & 0xFF,
        len(data) & 0xFF,
    ])
    return header + data


def decode_xml(frame: bytes) -> Tuple[int, ET.Element]:
    if len(frame) < 8:
        raise ValueError("Frame too short")
    version = frame[0]
    inverse = frame[1]
    if _inverse_byte(version) != inverse:
        raise ValueError("Invalid V2GTP version/inverse")
    payload_type = (frame[2] << 8) | frame[3]
    length = (frame[4] << 24) | (frame[5] << 16) | (frame[6] << 8) | frame[7]
    payload = frame[8:8+length]
    if len(payload) != length:
        raise ValueError("Incomplete payload")
    try:
        elem = ET.fromstring(payload.decode("utf-8"))
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML payload: {e}")
    return payload_type, elem


async def send_xml(writer: asyncio.StreamWriter, elem: ET.Element, payload_type: int = V2GTP_XML_PAYLOAD):
    frame = encode_xml(payload_type, elem)
    writer.write(frame)
    await writer.drain()


async def read_xml(reader: asyncio.StreamReader, timeout: float = 30.0) -> Tuple[int, ET.Element]:
    """Read V2GTP framed XML message with timeout."""
    try:
        # Read header first with timeout
        header = await asyncio.wait_for(reader.readexactly(8), timeout=timeout)
        version = header[0]
        inverse = header[1]
        if _inverse_byte(version) != inverse:
            raise ValueError("Invalid V2GTP version/inverse in stream")
        payload_type = (header[2] << 8) | header[3]
        length = (header[4] << 24) | (header[5] << 16) | (header[6] << 8) | header[7]
        
        # Validate payload length to prevent memory exhaustion
        if length > 10 * 1024 * 1024:  # 10MB max
            raise ValueError(f"Payload too large: {length} bytes")
        if length == 0:
            raise ValueError("Payload length is zero")
        
        payload = await asyncio.wait_for(reader.readexactly(length), timeout=timeout)
        try:
            elem = ET.fromstring(payload.decode("utf-8"))
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML payload: {e}")
        return payload_type, elem
    except asyncio.TimeoutError:
        raise ValueError(f"Read timeout after {timeout}s")
