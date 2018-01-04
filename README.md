# Shared-Stuff
- mpy-cross.exe: Windows version of Micropython cross-compiler for the MP version
- micropython.exe: Windows version of Micropython
- mpy-cross_pycom.exe: Windows version of Micropython cross-compiler for the pycom build
- mpy-cross_pycom_linux: Linux version for the Pycom branch
- mpy-cross_microython_org_linux: Linux version for the Micropython.org branch
- wipy_pycom_1.11.0.b1.bin and wipy_pycom_1.12.0.b1.bin: Variants of the pycom image for Wemos LOLIN32 lite or other ESP32 boards with a rev 1 chip but without SPIRAM.
Two major changes are included:  
  a) The call to get_revision() always returns 0, making the pycom image believe that
there is no SPIRam.  
  b) Pin names like "GPIO21" can be used, which match the numbers
printed on the LOLIN's PCB, limited to those GPIO's which are available on a WiPy board.  
This image also runs on other ESP32 boards like ESP32Thing, Huzzah ESP32, ...   
Some of these board require a lower baud rate for flashing.
Included in frozen bytecode is the editor pye and the module upysh, which provides some shell like commands.  
** This is just a hack and not meant to replace PyCom's boards. These images may not run an other boards, e.g. because components or manufacturing quality are worse **
- libesp32.a: A variant of this file, in which get_revision() is defined as weak
link. It therfore can be overriden by a homebrew version of get_revision().
The one I use (and placed into main.c) looks like:  
```
#if MICROPY_PY_FORCE_REV0
IRAM_ATTR uint32_t esp_get_revision(void)
{
    return 0;
}
#endif
```
- xtensa Instruction Set Architecture (ISA).pdf: assembler instruction set of the xtensa architecture, matching the esp8266
