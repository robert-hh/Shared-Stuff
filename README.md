# Shared-Stuff
- mpy-cross.exe: Windows version of Micropython cross-compiler for the MP version
- micropython.exe: Windows version of Micropython
- mpy-cross_pycom.exe: Windows version of Micropython cross-compiler for the pycom build
- mpy-cross_pycom_linux: Linux version for the Pycom branch
- mpy-cross_microython_org_linux: Linux version for the Micropython.org branch
- wipy_pycom_1.11.0.b1.bin: A variant of the pycom image for Wemos LOLIN32 lite and a rev 1 chip.
Two major changes are included: a) The call gto get_revision() always return 0, making the pycom imagebelieve that
there is no SPIRam and just 4 MB of flash. b) Pin names like "GPIO21" can be used, which match the numbers
printed on the LOLIN's PCB. This image also runs on other ESP32 boards like ESP32Thing, Huzzah ESP32, ...
Included in frozen bytecode is the editor pye and the module upysh, which provides some shell like commands.
- xtensa Instruction Set Architecture (ISA).pdf: assembler instruction set of the xtensa architecture, matching the esp8266
