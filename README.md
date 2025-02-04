# ModbusSimulator

This repo has a Modbus RTU client and server Modbus simulator using PyModbus simulator. 

You need a serial port simulator. 

Run `socat` on `Linux` with the following command
```
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```