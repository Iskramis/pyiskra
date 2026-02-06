import asyncio
from pyiskra.devices import Device
from pyiskra.adapters import RestAPI


device_ip = "10.34.94.11"
device_auth = {"username": "admin", "password": "iskra"}


async def main():
    # Set device IP address

    # Create adapter
    adapter = RestAPI(ip_address=device_ip, authentication=device_auth)

    # Create device
    device = await Device.create_device(adapter)

    # Initalize device
    await device.init()

    devices = [device]

    if device.is_gateway:
        devices += device.get_child_devices()

    for device in devices:
        # Update device status
        print(f"Updating status for {device.model} {device.serial}")
        await device.update_status()

        if device.supports_measurements:
            for index, phase in enumerate(device.measurements.phases):
                print(
                    f"Phase {index+1} - U: {phase.voltage.value} {phase.voltage.units}, I: {phase.current.value} {phase.current.units} P: {phase.active_power.value} {phase.active_power.units} Q: {phase.reactive_power.value} {phase.reactive_power.units} S: {phase.apparent_power.value} {phase.apparent_power.units} PF: {phase.power_factor.value} {phase.power_factor.units} PA: {phase.power_angle.value} {phase.power_angle.units} THD U: {phase.thd_voltage.value} {phase.thd_voltage.units} THD I: {phase.thd_current.value} {phase.thd_current.units}"
                )

        if device.supports_counters:
            for counter in device.counters.non_resettable:
                print(
                    f"Non-resettable counter, Value: {counter.value} {counter.units}, Direction: {counter.direction}"
                )

            for counter in device.counters.resettable:
                print(
                    f"Resettable counter, Value: {counter.value} {counter.units}, Direction: {counter.direction}"
                )
            print()

        if device.supports_time_blocks:
            for index, time_block in enumerate(device.time_blocks_measurements.time_blocks): 
                block = time_block.consumed_energy[index]
                print(f"Time block {index+1} - This Month: {block.this_month.value}{block.this_month.units}") 
                print(f"Time block {index+1} - Previous Month: {block.previous_month.value}{block.previous_month.units}") 
                print(f"Time block {index+1} - This Year: {block.this_year.value}{block.this_year.units}") 
                print(f"Time block {index+1} - Previous Year: {block.previous_year.value}{block.previous_year.units}") 
                print()

            for index, time_block in enumerate(device.time_blocks_measurements.time_blocks):
                block = time_block.excess_power[index]
                print(
                        f"Time block {index+1} Excess Power - This Month: {block.excess_power_this_month.value}{block.excess_power_this_month.units}, Previous Month: {block.excess_power_previous_month.value}{block.excess_power_previous_month.units}"
                )
                print()

            print(f"Active block: {device.time_blocks_measurements.active_block_index.value}{device.time_blocks_measurements.active_block_index.units}")
            print()

asyncio.run(main())
