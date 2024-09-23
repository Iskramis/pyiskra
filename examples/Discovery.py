from pyiskra.discovery import Discovery
from pyiskra.devices.BaseDevice import Device
from pyiskra.adapters import RestAPI, Modbus
from pyiskra.exceptions import DeviceConnectionError, ProtocolNotSupported


import asyncio
import logging
import netifaces


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

authentication = {"username": "admin", "password": "iskra"}


async def main():

    discovery = Discovery()
    # Get all network interfaces
    interfaces = netifaces.interfaces()
    # Get the broadcast addresses for each interface
    broadcast_addresses = []
    for interface in interfaces:
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            ipv4_addresses = addresses[netifaces.AF_INET]
            for address in ipv4_addresses:
                if "broadcast" in address:
                    broadcast_addresses.append(address["broadcast"])
    discovered_devices = await discovery.get_devices(broadcast_addresses)

    if not discovered_devices:
        logger.warning("No Iskra devices discovered.")
        return

    devices = []
    for device in discovered_devices:
        try:
            iskra_device = await Device.create_device(
                RestAPI(ip_address=device.ip_address, authentication=authentication)
            )
        except (DeviceConnectionError, ProtocolNotSupported) as e:
            try:
                iskra_device = await Device.create_device(
                    Modbus(
                        protocol="tcp",
                        ip_address=device.ip_address,
                        modbus_address=device.modbus_address,
                    )
                )
            except Exception as e:
                logger.error(
                    f"Failed to create Device object for {device.model} {device.serial}: {e}"
                )
                continue
        try:
            await iskra_device.init()
            devices.append(iskra_device)
        except Exception as e:
            logger.error(
                f"Failed to create Device object for {device.model} {device.serial}: {e}"
            )

    for device in devices.copy():
        if device.is_gateway:
            devices += device.get_child_devices()

    while True:
        for device in devices:
            logger.info(f"Updating status for {device.model} {device.serial}")
            await device.update_status()

            message = ""

            if device.supports_measurements:
                message += f"Timestamp: {device.measurements.timestamp}\n"
                for index, phase in enumerate(device.measurements.phases):
                    message += f"Phase {index+1} - U: {phase.voltage.value} {phase.voltage.units}, I: {phase.current.value} {phase.current.units} P: {phase.active_power.value} {phase.active_power.units} Q: {phase.reactive_power.value} {phase.reactive_power.units} S: {phase.apparent_power.value} {phase.apparent_power.units} PF: {phase.power_factor.value} {phase.power_factor.units} PA: {phase.power_angle.value} {phase.power_angle.units} THD U: {phase.thd_voltage.value} {phase.thd_voltage.units} THD I: {phase.thd_current.value} {phase.thd_current.units}\n"

            if device.supports_counters:
                for counter in device.counters.non_resettable:
                    message += f"Non-resettable counter, Value: {counter.value}{counter.units}, Direction: {counter.direction} \n"

                for counter in device.counters.resettable:
                    message += f"Resettable counter, Value: {counter.value}{counter.units}, Direction: {counter.direction} \n"

            logger.info(message)

        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
