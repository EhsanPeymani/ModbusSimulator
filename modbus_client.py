import logging
from pymodbus.client import ModbusSerialClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import yaml
import time
from utilities import ModbusDecoder


# Configure logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


class ModbusRTUClient:
    def __init__(self, config_file):
        # Load configuration
        with open(config_file, "r") as f:
            self.config = yaml.safe_load(f)

        # Create client
        self.client = ModbusSerialClient(
            port="/dev/pts/33",  # Use the other end of the virtual serial port
            baudrate=115200,
            parity="N",
            stopbits=1,
            bytesize=8,
        )

    def read_float(self, device_id, address):
        """Read a 32-bit float value from the specified address"""
        response = self.client.read_holding_registers(address, count=2, slave=device_id)
        if not response.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                response.registers, byteorder=Endian.BIG, wordorder=Endian.BIG
            )
            return decoder.decode_32bit_float()
        return None

    def read_string(self, device_id, address, length):
        """Read a string value from the specified address"""
        # Calculate number of registers needed (2 bytes per register)
        register_count = (length + 1) // 2
        response = self.client.read_holding_registers(
            address, count=register_count, slave=device_id
        )

        if not response.isError():
            # Convert registers to bytes
            bytes_list = []
            for register in response.registers:
                bytes_list.extend(register.to_bytes(2, byteorder="big"))

            # Convert bytes to string and strip null characters
            return bytes(bytes_list).decode("ascii").rstrip("\0")
        return None

    def read_all_values(self):
        """Read all configured values from the devices"""
        decoder = ModbusDecoder()
        for device in self.config["modbus_devices"]:
            device_id = device["device_id"]
            print(f"\nReading from Device {device_id} ({device['description']})")

            if "registers" in device:
                # Read SFP values
                if "sfps" in device["registers"]:
                    for sfp in device["registers"]["sfps"]:
                        print(f"\nSFP {sfp['sfp']}:")
                        rx_power = self.read_float(
                            device_id, sfp["rx_power"]["address"]
                        )
                        tx_power = self.read_float(
                            device_id, sfp["tx_power"]["address"]
                        )
                        temp = self.read_float(device_id, sfp["temperature"]["address"])

                        print(f"{rx_power:.2f} dBm, {tx_power:.2f} dBm, {temp:.2f} °C")

                # Read product info
                if "product_info" in device["registers"]:
                    product_info = device["registers"]["product_info"]
                    print("\nProduct Info:")

                    if "product_number" in product_info:
                        product_number = self.read_string(
                            device_id,
                            product_info["product_number"]["address"],
                            product_info["product_number"]["length"],
                        )
                        print(f"  Product Number: {product_number}")

                    if "serial_number" in product_info:
                        serial_number = self.read_string(
                            device_id,
                            product_info["serial_number"]["address"],
                            product_info["serial_number"]["length"],
                        )
                        print(f"  Serial Number: {serial_number}")

    def run(self):
        """Run the client and continuously read values"""
        if not self.client.connect():
            print("Failed to connect!")
            return

        try:
            while True:
                self.read_all_values()
                print("\n" + "=" * 50)
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nStopping client...")
        finally:
            self.client.close()


if __name__ == "__main__":
    # Create and start client
    client = ModbusRTUClient("resources/modbus_register_configuration.yaml")
    client.run()
