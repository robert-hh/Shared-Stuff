# Shared-Stuff
- mpy-cross_pycom.exe: Windows version of Micropython cross-compiler for the pycom build
- mpy-cross_pycom_linux: Linux version for the Pycom branch
- xtensa Instruction Set Architecture (ISA).pdf: assembler instruction set of the xtensa architecture, matching the esp8266
- samd_firmware: Firmware for a couple of SAMD21 and SAMD51 boards.
- w600_firmware: Firmware for a couple of W600 boards. These differ only in the definition of the boas pins in Pin.board. They all have threading and SSL enabled and use LFS for the internal file system.
- esp_hosted_airlift.bin: Firmware for the Airlift ESP32 modules to be used with the esp_hosted driver.
- NINA_FW_v1.5.0_Airlift.bin: Firmware for the Airlift ESP32 module to be used with the NINAW10 driver.
- NINA_FW_v1.5.0_W102.bin: Firmware for the W102 ESP32 module to be used with the NINAW10 driver.
- ninaflash.py: Sample script to upload the ESP32 software to a ESP32 WiFi/BLE module on the board. Requires espflash.py from micropython-lib. UART port, Reset and GPIO0 pins have to be adapted for the host port.
- espflash.py: Version of espflash.py which is less memory critical.

Some Pycom tarballs:

- HELTEC_WS-1.20.2.rc6.tar.gz   Tar-Ball for the Heltec Wireless Stick, 800-900MHz
- HELTEC_WSL-1.20.2.rc6.tar.gz  Tar-Ball for the Heltec Wireless Stick Lite, 800-900MHz

The difference between the two is the amount of flash which is assumed. 
8MB for the -WS and 4 MB for the -WSL board. 
