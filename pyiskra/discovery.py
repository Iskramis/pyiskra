import asyncio
import socket
import psutil
import logging
import ipaddress

log = logging.getLogger(__name__)

UDP_DST_PORT = 33333
RCV_BUFSIZ = 1024

GRACE_SECONDS = 5

DISCOVERY_MSG = b"\x00\x00\x00\x1a"


class DiscoveredDevice:
    @staticmethod
    def parse_UDP_discovery_info(discovery_info):
        data = {}
        if discovery_info[3] != int.from_bytes(b"\x1b"):
            raise AttributeError("Not device info")
        data["ssid"] = discovery_info[8:20].decode("utf-8").replace("\x00", "").strip()
        data["mac"] = discovery_info[20:25].hex(":")
        data["tcp"] = int.from_bytes(discovery_info[26:27])
        data["model"] = (
            discovery_info[28:42].decode("utf-8").replace("\x00", "").strip()
        )
        data["serial"] = (
            discovery_info[43:51].decode("utf-8").replace("\x00", "").strip()
        )
        data["modbus_address"] = discovery_info[136]
        data["sw_ver"] = discovery_info[52] / 100
        data["hw_ver"] = chr(discovery_info[54])
        try:
            data["description"] = (
                discovery_info[55:94].decode("utf-8").replace("\x00", "").strip()
            )
            data["location"] = (
                discovery_info[95:134].decode("utf-8").replace("\x00", "").strip()
            )
        except:
            pass
        return data

    def __init__(self, ip, port, basic_info_string):
        self.values = {}
        self.values["ip_address"] = ip
        self.values["port"] = port
        self.values.update(self.parse_UDP_discovery_info(basic_info_string))

    def __getattr__(self, name):
        return self.values[name]


class Discovery:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", 0))
        self.sock.settimeout(GRACE_SECONDS)

        self.cancel_event = asyncio.Event()
        self.dev = {}

    async def broadcast_udp_packet(self, ip_address):
        try:
            log.debug(f"Sending Broadcast to {ip_address}")
            await self.loop.sock_sendto(
                self.sock, DISCOVERY_MSG, (ip_address, UDP_DST_PORT)
            )
        except Exception as e:
            log.error(f"Error broadcasting to {ip_address}: {e}")
            raise e

    async def poll(self, stop_if_found=None, ip=None):
        try:
            if ip:
                broadcast_addresses = [ip]
            else:
                broadcast_addresses = []
                for interface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET:
                            network = ipaddress.IPv4Network(
                                f"{addr.address}/{addr.netmask}", strict=False
                            )
                            # remove local-link and loopback
                            if not addr.address.startswith(
                                "169.254"
                            ) and not addr.address.startswith("127."):
                                broadcast_addresses.append(
                                    str(network.broadcast_address)
                                )

            # Broadcast UDP packets to all IPs concurrently
            await asyncio.gather(
                *[
                    self.broadcast_udp_packet(ip_address)
                    for ip_address in broadcast_addresses
                ]
            )

            start_time = self.loop.time()
            while (
                not self.cancel_event.is_set()
                and (self.loop.time() - start_time) < GRACE_SECONDS
            ):
                try:
                    # Use asyncio.wait_for to set a timeout for sock_recvfrom
                    data, addr = await asyncio.wait_for(
                        self.loop.sock_recvfrom(self.sock, RCV_BUFSIZ), timeout=1.0
                    )
                    device = DiscoveredDevice(addr[0], addr[1], data)
                    log.info(
                        f"Found device {device.model} {device.serial} {device.ip_address}"
                    )
                    new_mac = device.mac
                    self.dev[new_mac] = device

                    if (
                        stop_if_found is not None
                        and device.serial.lower() == stop_if_found.lower()
                    ):
                        return list(self.dev.values())

                except asyncio.TimeoutError:
                    # Handle timeout and continue the loop
                    continue

                except ValueError as ve:
                    log.error(f"Error parsing discovery info: {ve}")
                    raise

        except Exception as e:
            log.error(f"Error during discovery: {e}")
            raise

        return list(self.dev.values())

    async def get_devices(self, ip=None):
        try:
            devices = await self.poll(ip=ip)
            return devices
        except Exception as e:
            log.error(f"Error getting devices: {e}")
            raise

    async def get_serial(self, serial):
        try:
            devices = await self.poll(serial)
            for device in devices:
                if device.serial.lower() == serial.lower():
                    return device
            return None
        except Exception as e:
            log.error(f"Error getting serial: {e}")
            raise
