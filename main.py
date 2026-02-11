import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


async def run_cloud(host: str, port: int):
    from cloud.server import CloudServer

    server = CloudServer(host=host, port=port)
    await server.run()


async def run_station(host: str, port: int, cloud_host: str, cloud_port: int, use_pqc: bool = False):
    from ev_station.server_new import StationServer
    if use_pqc:
        logger.info("Starting Station with PQC application-layer signatures (Falcon-512)")
    else:
        logger.info("Starting Station with Classical cryptography")
    station = StationServer(bind_host=host, bind_port=port, cloud_host=cloud_host, cloud_port=cloud_port, use_pqc_tls=False)
    await station.start()
    logger.info("SECC station running at %s:%d (cloud %s:%d) [PQC: %s]", host, port, cloud_host, cloud_port, use_pqc)
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("SECC station shutting down...")
        await station.stop()


async def run_vehicle(station_host: str, station_port: int, use_pqc: bool = False):
    from ev_vehicle.client_new import VehicleClient
    if use_pqc:
        logger.info("Starting Vehicle with PQC application-layer signatures (Falcon-512)")
    else:
        logger.info("Starting Vehicle with Classical cryptography")
    client = VehicleClient(station_host=station_host, station_port=station_port, use_pqc_tls=False)
    await client.run_session()


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Post-Quantum Secure EV Charging Infrastructure")
    parser.add_argument("--mode", required=True, choices=["cloud", "station", "vehicle"], help="Which component to run")
    parser.add_argument("--host", required=True, help="Host/IP for server bind or station host for vehicle")
    parser.add_argument("--port", required=True, type=int, help="Port to bind/connect")
    parser.add_argument("--cloud-host", help="Cloud host for station")
    parser.add_argument("--cloud-port", type=int, help="Cloud port for station")
    parser.add_argument("--pqc", action="store_true", help="Use PQC certificates (ML-DSA)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    if args.mode == "cloud":
        coro = run_cloud(args.host, args.port)
    elif args.mode == "station":
        if not args.cloud_host or not args.cloud_port:
            print("--cloud-host and --cloud-port required for station mode", file=sys.stderr)
            sys.exit(2)
        coro = run_station(args.host, args.port, args.cloud_host, args.cloud_port, use_pqc=args.pqc)
    elif args.mode == "vehicle":
        coro = run_vehicle(args.host, args.port, use_pqc=args.pqc)
    else:
        print("Unknown mode", file=sys.stderr)
        sys.exit(2)

    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
