import espflash
from machine import Pin
from machine import UART
import sys
sys.path.append("/")

if True:
    reset = Pin("D12", Pin.OUT)
    gpio0 = Pin("D10", Pin.OUT)
    uart = UART(3, 115200, tx=Pin("D1"), rx=Pin("D0"), timeout=350)

    md5sum = b"b0b9ab23da820a469e597c41364acb3a"
    path = "/remote/NINA_FW_v1.5.0_Airlift.bin"
    # md5sum = b"28ab84372ff4f07551b984671f7f9ff9"
    # path = "/remote/esp_hosted_airlift.bin"

    esp = espflash.ESPFlash(reset, gpio0, uart)
    # Enter bootloader download mode, at 115200
    esp.bootloader()
    # Can now chage to higher/lower baudrate
    esp.set_baudrate(921600)
    # Must call this first before any flash functions.
    esp.flash_attach()
    # Read flash size
    size = esp.flash_read_size()
    # Configure flash parameters.
    esp.flash_config(size)
    # Write firmware image from internal storage.
    esp.flash_write_file(path)
    # Compares file and flash MD5 checksum.
    esp.flash_verify_file(path, md5sum)
    # Resets the ESP32 chip.
    esp.reboot()
