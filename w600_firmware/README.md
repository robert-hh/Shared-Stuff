MicroPython port to the W60X
=============================

W60X is an embedded Wi-Fi SoC chip which is complying with IEEE802.11b/g/n international
standard and which supports multi interface, multi protocol.
It can be easily applied to smart appliances, smart home, health care, smart toy, wireless audio & video,
industrial and other IoT fields.
This SoC integrates Cortex-M3 CPU, Flash, RF Transceiver, CMOS PA, BaseBand.
It applies multi interfaces such as SPI, UART, GPIO, I2C, PWM, I2S, 7816.
It applies multi encryption and decryption protocols such as PRNG/SHA1/MD5/RC4/DES/3DES/AES/CRC/RSA.

This is an experimental port of MicroPython to the WinnerMicro W60X microcontroller.  

Supported features
------------------------------------

- REPL (Python prompt) over UART0.
- 8k stack for the MicroPython task and 100k Python heap.
- Most of MicroPython's features are enabled: unicode, arbitrary-precision integers,
  single-precision floats (30bit), frozen bytecode, native emitters (native, viper and arm_thumb),
  framebuffer, asyncio, as well as many of the internal modules.
- The machine module with mem8..mem32, GPIO, UART, SPI, I2C, PWM, WDT, ADC, RTC and Timer.
- The network module with WLAN (WiFi) support (including OneShot).
- Support of SSL using hardware encryption and decryption.
- Internal LFS2 filesystem using the flash (up to ~300 KB available, up to ~1.3 MB on 2MB flash devices,
depending on the build flags setting).
- Built-in FTP server for transfer of script files.

Setting up the cross toolchain and WM_SDK
-----------------------------------------

Supports direct compilation in Linux system and compilation in Cygwin environment in Windows system.

There are two main things to do here:

- Download the cross toolchain and add it to the environment variable
- Download WM_SDK and add to environment variables

The cross toolchain used is arm-none-eabi-gcc version where the download address is
[GNU Arm Embedded Toolchain](https://launchpad.net/gcc-arm-embedded/4.9/4.9-2014-q4-major)

You will need to update your `PATH` environment variable to include the cross toolchain. For example, you can issue the following commands on (at least) Linux:

    $ export PATH=$PATH:/opt/tools/arm-none-eabi-gcc/bin

You can put this command in your `.profile` or `.bash_login` (or `.bashrc` if using Github Codespaces).

WM_SDK initially required the 4.x version of the GCC cross-compiler for compiling. Note also that version 4.x of the cross-compiler is 32bit and you may need `sudo apt install lib32z1` if running on a 64bit Linux host (test by running `arm-none-eabi-gcc --version` -- if it runs, you're fine; if you get a bash "No such file or directory", first double-check your $PATH and, if $PATH is correct, then it's the 32bit issue).
Newer 64 bit versions of the GCC cross compiler like 8.3, 10.3 and 11.2 have been verified to work as well. 

WM_SDK download address is [W60X_SDK](http://www.winnermicro.com/en/html/1/156/158/497.html), under the Software Data tab. WM_SDK must be G3.01 and newer versions (G3.04 is latest as of end of 2022). You can also consider using the Github repo https://github.com/robert-hh/WM_SDK_W60X.

You will need to update your `PATH` environment variable to include the path of WM_SDK. For example, you can issue the following commands on (at least) Linux:

    $ export WMSDK_PATH=/home/username/WM_SDK

You can put this command in your `.profile` or `.bash_login` (or `.bashrc` if using Github Codespaces).

You also need to modify the build configuration file in WM_SDK, located at: `WM_SDK/Include/wm_config.h`

You can crop the component by modifying the macro switch, For example, 

    #define TLS_CONFIG_HOSTIF CFG_OFF

The recommended components that can be turned off are:

    #define TLS_CONFIG_HOSTIF      CFG_OFF
    #define TLS_CONFIG_RMMS        CFG_OFF
    #define TLS_CONFIG_HTTP_CLIENT CFG_OFF
    #define TLS_CONFIG_NTP         CFG_OFF

Building the firmware
---------------------

Build MicroPython for a generic board:
```
bash
$ cd mpy-cross
$ make

$ cd ports/w60x
$ make submodules
$ make V=s BOARD=GENERIC
```
This will produce binary firmware images in the `build-GENERIC` subdirectory.
There are several options that can be modified in the Makefile.
They are described in the separate file: `Makefile_build_options.txt`.

Instead of BOARD=GENERIC another board may be selected.
Currently available selections are:

- GENERIC
- THINGSTURN_TB01
- W600_EVB_V2
- WAVGAT_AIR602
- WEMOS_W600
- WIS600

The firmware of these boards on differs in the set of Pin objects defined in machine.Pin.board.

Flashing the Firmware
-----------------------

To upload the firmware to the target board, please use the command 
```
bash
make V=s BOARD=GENERIC flash
```
Some boards like the Wemos W600 require pushing reset at the start of the upload while the
upload tool waits for synchronisation with the target board.
Connecting pin PA0 to GND while pushing reset will ensure that the bootloader of the board
will start and go into synchronization mode to allow the upload.
Once the new Micropython firmware is on the board this connection of PA0 to GND is no longer necessary.
Then you also may execute `machine.bootloader` from within Micropython to start the bootloader.

Reference documents
-----------------------
Visit [WinnerMicro](http://www.winnermicro.com/en/html/1/156/158/497.html) for more documentation.

