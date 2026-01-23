import asyncio
from pyiskra.devices import Device
from pyiskra.adapters import Modbus


async def main():

    # Create adapter
    adapter = Modbus(protocol="rtu", port="COM12")

    await adapter.get_basic_info()

    # Create device
    device = await Device.create_device(adapter)

    # Initalize device
    await device.init()

    # Update device status
    print(f"Updating status for {device.model} {device.serial}")
    await device.update_status()

    print()
    if device.supports_measurements:
        for index, phase in enumerate(device.measurements.phases):
            print(
                f"Phase {index+1} - U: {phase.voltage.value}{phase.voltage.units}, I: {phase.current.value}{phase.current.units} P: {phase.active_power.value}{phase.active_power.units} Q: {phase.reactive_power.value}{phase.reactive_power.units} S: {phase.apparent_power.value}{phase.apparent_power.units} PF: {phase.power_factor.value}{phase.power_factor.units} PA: {phase.power_angle.value}{phase.power_angle.units} THD U: {phase.thd_voltage.value}{phase.thd_voltage.units} THD I: {phase.thd_current.value}{phase.thd_current.units}"
            )

    print()
    if device.supports_counters:
        for counter in device.counters.non_resettable:
            print(
                f"Non-resettable counter, Value: {counter.value}{counter.units}, Direction: {counter.direction}"
            )

        for counter in device.counters.resettable:
            print(
                f"Resettable counter Value: {counter.value}{counter.units}, Direction: {counter.direction}"
            )

    print()
    if device.supports_iMC_functions:
        for index, time_block in enumerate(device.Time_Blocks_Measurements.time_blocks): 
            block = time_block.consumed_energy[index]
            print(f"Time block {index+1} - This Month: {block.this_month.value}{block.this_month.units}") 
            print(f"Time block {index+1} - Previous Month: {block.previous_month.value}{block.previous_month.units}") 
            print(f"Time block {index+1} - This Year: {block.this_year.value}{block.this_year.units}") 
            print(f"Time block {index+1} - Previous Year: {block.previous_year.value}{block.previous_year.units}") 
            print(f"Time block {index+1} - Total: {block.total.value}{block.total.units}, timestamp: {block.timestamp_total.value}")
            print(f"Time block {index+1} - Last Month Capture: {block.last_month.value}{block.last_month.units}, timestamp: {block.timestamp_last_month.value}") 
            print(f"Time block {index+1} - 2 Months ago Capture: {block.two_months_ago.value}{block.two_months_ago.units}, timestamp: {block.timestamp_two_months_ago.value}") 
            print(f"Time block {index+1} - Last Year Capture: {block.last_year.value}{block.last_year.units}, timestamp: {block.timestamp_last_year.value}") 
            print(f"Time block {index+1} - 2 Years ago Capture: {block.two_years_ago.value}{block.two_years_ago.units}, timestamp: {block.timestamp_two_years_ago.value}")
            print()

        for index, time_block in enumerate(device.Time_Blocks_Measurements.time_blocks):
            block = time_block.excess_power[index]
            print(
                f"Time block {index+1} Excess Power - Total: {block.excess_power_limit.value}{block.excess_power_limit.units}, This Month: {block.excess_power_this_month.value}{block.excess_power_this_month.units}, Previous Month: {block.excess_power_previous_month.value}{block.excess_power_previous_month.units}"
            )
            print()

        for index, time_block in enumerate(device.Time_Blocks_Measurements.time_blocks):
            block = time_block.max_15min_Power[index]
            print(f"Time block {index+1} - Since reset: {block.max_15min_power_since_reset.value}{block.max_15min_power_since_reset.units}, timestamp: {block.timestamp_since_reset.value}")
            print(f"Time block {index+1} - This Month: {block.max_15min_power_this_month.value}{block.max_15min_power_this_month.units}, timestamp: {block.timestamp_this_month.value}") 
            print(f"Time block {index+1} - Previous Month: {block.max_15min_power_previous_month.value}{block.max_15min_power_previous_month.units}, timestamp: {block.timestamp_previous_month.value}") 
            print(f"Time block {index+1} - This Year: {block.max_15min_power_this_year.value}{block.max_15min_power_this_year.units}, timestamp: {block.timestamp_this_year.value}") 
            print(f"Time block {index+1} - Previous Year: {block.max_15min_power_previous_year.value}{block.max_15min_power_previous_year.units}, timestamp: {block.timestamp_previous_year.value}")
            print(f"Time block {index+1} - Reset timestamp: {block.reset_timestamp.value}{block.reset_timestamp.units}")
            print()

        imports = device.Time_Blocks_Measurements.active_power_measurements_import
        print(f"Import(+) - Actual value: {imports.actual_value.value}{imports.actual_value.units}")
        print(f"Import(+) - Thermal function: {imports.thermal_function.value}{imports.thermal_function.units}")  
        print(f"Import(+) - Predicted 15min: {imports.predicted_15min.value}{imports.predicted_15min.units}") 
        print(f"Import(+) - Predicted 15min / active limit: {imports.predicted_15min_active_limit.value}{imports.predicted_15min_active_limit.units}") 
        print(f"Import(+) - Last 15min: {imports.last_15min.value}{imports.last_15min.units}") 
        print(f"Import(+) - Max 15min since reset: {imports.max_15min_since_reset.value}{imports.max_15min_since_reset.units}") 
        print(f"Import(+) - timestamp: {imports.timestamp.value}{imports.timestamp.units}") 
        print(f"Import(+) - Total: {imports.active_energy_total.value}{imports.active_energy_total.units}") 
        print()

        exports = device.Time_Blocks_Measurements.active_power_measurements_export
        print(f"Export(-) - Actual value: {exports.actual_value.value}{exports.actual_value.units}")
        print(f"Export(-) - Thermal function: {exports.thermal_function.value}{exports.thermal_function.units}")  
        print(f"Export(-) - Predicted 15min: {exports.predicted_15min.value}{exports.predicted_15min.units}") 
        print(f"Export(-) - Last 15min: {exports.last_15min.value}{exports.last_15min.units}") 
        print(f"Export(-) - Max 15min since reset: {exports.max_15min_since_reset.value}{exports.max_15min_since_reset.units}") 
        print(f"Export(-) - Timetamp: {exports.timestamp.value}{exports.timestamp.units}")
        print(f"Export(-) - Total: {exports.active_energy_total.value}{exports.active_energy_total.units}")
        print()

        print(f"Active block: {device.Time_Blocks_Measurements.active_block_index.value}{device.Time_Blocks_Measurements.active_block_index.units}")
        print(f"Time to end interval: {device.Time_Blocks_Measurements.time_to_end_interval.value}{device.Time_Blocks_Measurements.time_to_end_interval.units}") 
        print()

asyncio.run(main())
