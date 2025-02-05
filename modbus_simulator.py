import logging
from pymodbus.server import StartSerialServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
import struct
import random
import yaml
import time
import threading

# Configure logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


class ModbusRTUSimulator:
    def __init__(self, config_file):
        # Load configuration
        with open(config_file, "r") as f:
            self.config = yaml.safe_load(f)

        # Create a ModbusServerContext with a single slave context
        self.context = self._setup_server_context()

    def _create_slave_context(self) -> ModbusSlaveContext:
        """Create a ModbusSlaveContext for the specified device"""
        hr = ModbusSequentialDataBlock(0, [0] * 65536)
        ir = ModbusSequentialDataBlock(0, [0] * 65536)

        return ModbusSlaveContext(hr=hr, ir=ir, zero_mode=True)

    def _setup_server_context(self):
        """Setup server context for both devices"""
        contexts = {}
        slave_context = self._create_slave_context()

        for device in self.config["modbus_devices"]:
            device_id = device["device_id"]

            if device_id not in [1, 2]:
                continue

            # Initialize device data
            if "registers" in device:
                if device_id == 1 and "sfps" in device["registers"]:
                    self.init_sfp_data(slave_context, device["registers"]["sfps"])
                elif device_id == 2 and "product_info" in device["registers"]:
                    self.init_product_info(
                        slave_context, device["registers"]["product_info"]
                    )

            contexts[device_id] = slave_context

        return ModbusServerContext(slaves=contexts, single=False)

    def init_sfp_data(self, context, sfps):
        """Initialize SFP data with base values"""
        sfp_base_values = {
            1: {"tx": 3.0, "rx": 0.1},
            2: {"tx": 3.0, "rx": 0.1},
            3: {"tx": 3.0, "rx": 0.1},
            4: {"tx": 3.0, "rx": 0.1},
        }

        for sfp in sfps:
            sfp_id = sfp["sfp"]
            if sfp_id in sfp_base_values:
                base = sfp_base_values[sfp_id]
                self.write_float(context, sfp["tx_power"]["address"], base["tx"])
                self.write_float(context, sfp["rx_power"]["address"], base["rx"])
                self.write_float(context, sfp["temperature"]["address"], 25.0)

    def update_sfp_values(self, slave_context, sfps):
        """Update SFP values with specified variations"""
        sfp_base_values = {
            1: {"tx": 3.0, "rx": 0.07},
            2: {"tx": 3.0, "rx": 0.07},
            3: {"tx": 3.0, "rx": 0.07},
            4: {"tx": 3.0, "rx": 0.07},
        }

        for sfp in sfps:
            sfp_num = sfp["sfp"]
            if sfp_num in sfp_base_values:
                base = sfp_base_values[sfp_num]

                # Add random variations
                tx_power = base["tx"] + random.uniform(-0.05, 0.05)
                rx_power = base["rx"] + random.uniform(-0.03, 0.03)
                temperature = 25.0 + random.uniform(-1, 1)

                # Write values to registers
                self.write_float(slave_context, sfp["tx_power"]["address"], tx_power)
                self.write_float(slave_context, sfp["rx_power"]["address"], rx_power)
                self.write_float(
                    slave_context, sfp["temperature"]["address"], temperature
                )
                
        log.info(f"=== Completed SFP update at {time.strftime('%Y-%m-%d %H:%M:%S')} === ")

    def init_product_info(self, context, product_info):
        # Write sample product and serial numbers
        if "product_number" in product_info:
            self.write_string(
                context,
                product_info["product_number"]["address"],
                "PROD123456",
                product_info["product_number"]["length"],
            )

        if "serial_number" in product_info:
            self.write_string(
                context,
                product_info["serial_number"]["address"],
                "SN987654321",
                product_info["serial_number"]["length"],
            )

    def update_product_info(
        self, slave_context, product_info, product_number, serial_number
    ):
        """Update product info registers with provided values"""
        if "product_number" in product_info:
            self.write_string(
                slave_context,
                product_info["product_number"]["address"],
                product_number,
                product_info["product_number"]["length"],
            )

        if "serial_number" in product_info:
            self.write_string(
                slave_context,
                product_info["serial_number"]["address"],
                serial_number,
                product_info["serial_number"]["length"],
            )
        log.info("=== Completed Product Info update ===")

    def write_float(self, context, address, value):
        """Write a float value to the specified address"""
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        builder.add_32bit_float(value)
        registers = builder.to_registers()
        context.setValues(3, address, registers)

    def write_string(self, context, address, value, length):
        # Pad string to specified length
        padded_value = value.ljust(length, "\0")
        # Convert to bytes and then to registers (2 bytes per register)
        bytes_value = padded_value.encode("ascii")
        registers = [
            struct.unpack(">H", bytes_value[i : i + 2])[0]
            for i in range(0, len(bytes_value), 2)
        ]
        context.setValues(3, address, registers)

    def update_values(self):
        """Periodically update all values to simulate real-time changes"""
        counter = 0
        while True:
            for device in self.config["modbus_devices"]:
                device_id = device["device_id"]

                if device_id not in [1, 2]:
                    continue

                slave_context = self.context[device_id]

                if "registers" in device:
                    # Update SFP values every second for device 1
                    if device_id == 1 and "sfps" in device["registers"]:
                        self.update_sfp_values(
                            slave_context, device["registers"]["sfps"]
                        )

                    # Update product info every 5 seconds for device 2
                    elif (
                        device_id == 2
                        and counter % 10 == 0
                        and "product_info" in device["registers"]
                    ):
                        self.update_product_info(
                            slave_context,
                            device["registers"]["product_info"],
                            "PROD-12",
                            "SN-Q10",
                        )

            counter += 1
            time.sleep(1)  # Update every second

    def start_server(self):
        """Start Modbus RTU server for device_id 2"""
        for device in self.config["modbus_devices"]:
            device_id = device["device_id"]

            if device_id not in [1, 2]:
                continue

            identity = ModbusDeviceIdentification()
            identity.VendorName = "Simulator"
            identity.ProductCode = f"Device{device_id}"
            identity.ModelName = device.get("description", f"Device {device_id}")

            # Start update thread for dynamic values
            update_thread = threading.Thread(target=self.update_values, daemon=True)
            update_thread.start()

            # Start server
            StartSerialServer(
                context=self.context,
                identity=identity,
                port="/dev/pts/13",
                baudrate=device["baudrate"],
            )


if __name__ == "__main__":
    # Create and start simulator
    simulator = ModbusRTUSimulator("modbus_register_configuration.yaml")

    try:
        print("Starting Modbus RTU simulator...")
        print("Press Ctrl+C to stop")
        simulator.start_server()
    except KeyboardInterrupt:
        print("\nStopping simulator...")
