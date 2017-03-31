# Shared-Stuff
- mcuimg.bin: build for wipy w/o threading, but support of .mpy files
- firmware-combined.bin: esp8266 build with frozen FTP server, upysh and editor, but w/o berkeley db
- firmware-combined-RS1.bin: esp8266 build with frozen FTP server, upysh and editor, but w/o berkeley db,
and RESERVED_SEC set to 1, giving 4k space for native code in flash
- firmware.bin: esp32 build with embedded ftp server, upysh and editor
- mpy-cross.exe: Windows version of Micropython cross-compiler for the MP version
- micropython.exe: Windows version of Micropython
- mpy-cross_pycom.exe: Windows version of Micropython cross-compiler for the pycom build
- mpy-cross_pycom_linux: Linux version for the Pycom branch
- esp8266-technical_reference_en.pdf: esp8266 technical reference from espressif's web site
- xtensa Instruction Set Architecture (ISA).pdf: assembler instruction set of the xtensa architecture, matching the esp8266
