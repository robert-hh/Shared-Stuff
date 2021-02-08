#!/usr/bin/env python3

"""
MicroPython Remote - Interaction and automation tool for MicroPython
MIT license; Copyright (c) 2019-2020 Damien P. George

This program provides a set of utilities to interact with and automate a
MicroPython device over a serial connection.  Commands supported are:

    mpr                         -- auto-detect, connect and enter REPL

    mpr <device-shortcut>       -- connect to given device
    mpr connect <device>        -- connect to given device
    mpr mount <local-dir>       -- mount local directory on device

    mpr eval <string>           -- evaluate and print the string
    mpr exec <string>           -- execute the string
    mpr fs <command> <args...>  -- execute filesystem commands on the device
    mpr repl                    -- enter REPL
    mpr run <script>            -- run the given local script

Multiple commands can be specified and they will be run sequentially.  The
serial device will be automatically detected if not specified.  If no action
is specified then the REPL will be entered.

Examples:
    mpr
    mpr a1
    mpr connect /dev/ttyUSB0 repl
    mpr ls
    mpr a1 ls
    mpr exec "import micropython; micropython.mem_info()"
    mpr eval 1/2 eval 3/4
    mpr mount .
    mpr mount . exec "import local_script"
    mpr ls
    mpr cat boot.py
"""

import os, re, struct, sys, time
import serial, serial.tools.list_ports

try:
    import select, termios
except ImportError:
    termios = None
    select = None
    import msvcrt

import pyboard


# TODO load aliases and device-shorcuts from .mprrc/.mprconfig
command_aliases = {
    "r": "repl",
    "ls": "fs ls",
    "cp": "fs cp",
    "rm": "fs rm",
    "mkdir": "fs mkdir",
    "cat": "fs cat",
    "bl": [
        "exec",
        "import machine; machine.Timer(period=1000, callback=lambda t: machine.bootloader())",
    ],
    "setrtc": ["exec", "import machine; machine.RTC().datetime((2020, 1, 1, 0, 10, 0, 0, 0))"],
}

device_shortcuts = {
    "a0": "/dev/ttyACM0",
    "a1": "/dev/ttyACM1",
    "a2": "/dev/ttyACM2",
    "u0": "/dev/ttyUSB0",
    "u1": "/dev/ttyUSB1",
    "u2": "/dev/ttyUSB2",
    "u3": "/dev/ttyUSB3",
    "c3": "COM3",
    "c4": "COM4",
    "c5": "COM5",
    "c6": "COM6",
}

fs_hook_cmds = {
    "CMD_STAT": 1,
    "CMD_ILISTDIR_START": 2,
    "CMD_ILISTDIR_NEXT": 3,
    "CMD_OPEN": 4,
    "CMD_CLOSE": 5,
    "CMD_READ": 6,
    "CMD_WRITE": 7,
    "CMD_SEEK": 8,
    "CMD_REMOVE": 9,
    "CMD_RENAME": 10,
}

fs_hook_code = """\
import os, io, ustruct as struct, micropython, sys


class RemoteCommand:
    def __init__(self, use_second_port):
        self.buf4 = bytearray(4)
        try:
            import pyb
            self.fout = pyb.USB_VCP()
            if self.use_second_port:
                self.fin = pyb.USB_VCP(1)
            else:
                self.fin = pyb.USB_VCP()
            import select
            self.poller = select.poll()
            self.poller.register(self.fin, select.POLLIN)
        except:
            # TODO sys.stdio doesn't support polling
            import sys
            self.fout = sys.stdout.buffer
            self.fin = sys.stdin.buffer

    def poll_in(self):
        if hasattr(self, 'poller'):
            for _ in self.poller.ipoll(1000):
                return
            self.end()
            raise Exception('timeout waiting for remote')

    def rd(self, n):
        buf = bytearray(n)
        self.rd_into(buf, n)
        return buf

    def rd_into(self, buf, n):
        # implement reading with a timeout in case other side disappears
        if n == 0:
            return
        self.poll_in()
        r = self.fin.readinto(buf, n)
        if r < n:
            mv = memoryview(buf)
            while r < n:
                self.poll_in()
                r += self.fin.readinto(mv[r:], n - r)

    def begin(self, type):
        micropython.kbd_intr(-1)
        buf4 = self.buf4
        if hasattr(self.fin, 'any'):
            while self.fin.any():
                self.fin.readinto(buf4, 1)
        buf4[0] = 0x18
        buf4[1] = type
        self.fout.write(buf4, 2)

    def end(self):
        micropython.kbd_intr(3)

    def rd_s8(self):
        self.rd_into(self.buf4, 1)
        n = self.buf4[0]
        if n & 0x80:
            n -= 0x100
        return n

    def rd_s32(self):
        buf4 = self.buf4
        self.rd_into(buf4, 4)
        n = buf4[0] | buf4[1] << 8 | buf4[2] << 16 | buf4[3] << 24
        if buf4[3] & 0x80:
            n -= 0x100000000
        return n

    def rd_u32(self):
        buf4 = self.buf4
        self.rd_into(buf4, 4)
        return buf4[0] | buf4[1] << 8 | buf4[2] << 16 | buf4[3] << 24

    def rd_bytes(self, buf):
        n = self.rd_s32()
        if buf is None:
            ret = buf = bytearray(n)
        else:
            ret = n
        self.rd_into(buf, n)
        return ret

    def rd_str(self):
        n = self.rd_s32()
        if n == 0:
            return ''
        else:
            return str(self.rd(n), 'utf8')

    def wr_s8(self, i):
        self.buf4[0] = i
        self.fout.write(self.buf4, 1)

    def wr_s32(self, i):
        struct.pack_into('<i', self.buf4, 0, i)
        self.fout.write(self.buf4)

    def wr_bytes(self, b):
        self.wr_s32(len(b))
        self.fout.write(b)

    # str and bytes act the same in MicroPython
    wr_str = wr_bytes


class RemoteFile(io.IOBase):
    def __init__(self, cmd, fd, is_text):
        self.cmd = cmd
        self.fd = fd
        self.is_text = is_text

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        self.close()

    def ioctl(self, request, arg):
        if request == 4:  # CLOSE
            self.close()
        return 0

    def flush(self):
        pass

    def close(self):
        if self.fd is None:
            return
        c = self.cmd
        c.begin(CMD_CLOSE)
        c.wr_s8(self.fd)
        c.end()
        self.fd = None

    def read(self, n=-1):
        c = self.cmd
        c.begin(CMD_READ)
        c.wr_s8(self.fd)
        c.wr_s32(n)
        data = c.rd_bytes(None)
        c.end()
        if self.is_text:
            data = str(data, 'utf8')
        else:
            data = bytes(data)
        return data

    def readinto(self, buf):
        c = self.cmd
        c.begin(CMD_READ)
        c.wr_s8(self.fd)
        c.wr_s32(len(buf))
        n = c.rd_bytes(buf)
        c.end()
        return n

    def write(self, buf):
        c = self.cmd
        c.begin(CMD_WRITE)
        c.wr_s8(self.fd)
        c.wr_bytes(buf)
        n = c.rd_s32()
        c.end()
        return n

    def seek(self, n):
        c = self.cmd
        c.begin(CMD_SEEK)
        c.wr_s8(self.fd)
        c.wr_s32(n)
        n = c.rd_s32()
        c.end()
        return n


class RemoteFS:
    def __init__(self, cmd):
        self.cmd = cmd

    def mount(self, readonly, mkfs):
        pass

    def umount(self):
        pass

    def chdir(self, path):
        if path.startswith('/'):
            self.path = path
        else:
            self.path += path
        if not self.path.endswith('/'):
            self.path += '/'

    def getcwd(self):
        return self.path

    def remove(self, path):
        c = self.cmd
        c.begin(CMD_REMOVE)
        c.wr_str(self.path + path)
        res = c.rd_s32()
        c.end()
        if res < 0:
            raise OSError(-res)

    def rename(self, old, new):
        c = self.cmd
        c.begin(CMD_RENAME)
        c.wr_str(self.path + old)
        c.wr_str(self.path + new)
        res = c.rd_s32()
        c.end()
        if res < 0:
            raise OSError(-res)

    def stat(self, path):
        c = self.cmd
        c.begin(CMD_STAT)
        c.wr_str(self.path + path)
        res = c.rd_s8()
        if res < 0:
            c.end()
            raise OSError(-res)
        mode = c.rd_u32()
        size = c.rd_u32()
        atime = c.rd_u32()
        mtime = c.rd_u32()
        ctime = c.rd_u32()
        c.end()
        return mode, 0, 0, 0, 0, 0, size, atime, mtime, ctime

    def ilistdir(self, path):
        c = self.cmd
        c.begin(CMD_ILISTDIR_START)
        c.wr_str(self.path + path)
        c.end()
        def next():
            while True:
                c.begin(CMD_ILISTDIR_NEXT)
                name = c.rd_str()
                if name:
                    type = c.rd_u32()
                    c.end()
                    yield (name, type, 0)
                else:
                    c.end()
                    break
        return next()

    def open(self, path, mode):
        c = self.cmd
        c.begin(CMD_OPEN)
        c.wr_str(self.path + path)
        c.wr_str(mode)
        fd = c.rd_s8()
        c.end()
        if fd < 0:
            raise OSError(-fd)
        return RemoteFile(c, fd, mode.find('b') == -1)


def __mount(use_second_port):
    os.mount(RemoteFS(RemoteCommand(use_second_port)), '/remote')
    os.chdir('/remote')
"""

# Apply basic compression on hook code.
for key, value in fs_hook_cmds.items():
    fs_hook_code = re.sub(key, str(value), fs_hook_code)
fs_hook_code = re.sub(" *#.*$", "", fs_hook_code, flags=re.MULTILINE)
fs_hook_code = re.sub("\n\n+", "\n", fs_hook_code)
fs_hook_code = re.sub("    ", " ", fs_hook_code)
fs_hook_code = re.sub("rd_", "r", fs_hook_code)
fs_hook_code = re.sub("wr_", "w", fs_hook_code)
fs_hook_code = re.sub("buf4", "b4", fs_hook_code)


def find_serial_device(dev):
    ports = serial.tools.list_ports.comports()
    if dev is None:
        for dev in device_shortcuts.values():
            if any(p.device == dev for p in ports):
                return dev
        print("no device found")
        sys.exit(1)
    else:
        dev = device_shortcuts.get(dev, dev)
        if any(p.device == dev for p in ports):
            return dev
        print(f"{dev} could not be accessed")
        sys.exit(1)


class ConsolePosix:
    def __init__(self):
        self.infd = sys.stdin.fileno()
        self.infile = sys.stdin.buffer.raw
        self.outfile = sys.stdout.buffer.raw
        self.orig_attr = termios.tcgetattr(self.infd)

    def enter(self):
        # attr is: [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        attr = termios.tcgetattr(self.infd)
        attr[0] &= ~(
            termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON
        )
        attr[1] = 0
        attr[2] = attr[2] & ~(termios.CSIZE | termios.PARENB) | termios.CS8
        attr[3] = 0
        attr[6][termios.VMIN] = 1
        attr[6][termios.VTIME] = 0
        termios.tcsetattr(self.infd, termios.TCSANOW, attr)

    def exit(self):
        termios.tcsetattr(self.infd, termios.TCSANOW, self.orig_attr)

    def readchar(self):
        res = select.select([self.infd], [], [], 0)
        if res[0]:
            return self.infile.read(1)
        else:
            return None

    def write(self, buf):
        self.outfile.write(buf)


class ConsoleWindows:
    def enter(self):
        pass

    def exit(self):
        pass

    def inWaiting(self):
        return 1 if msvcrt.kbhit() else 0

    def readchar(self):
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            while ch in b"\x00\xe0":  # arrow or function key prefix?
                if not msvcrt.kbhit():
                    return None
                ch = msvcrt.getch()  # second call returns the actual key code
                try:
                    ch = b"\x1b[" + {b"H": b"A",  # UP
                                     b"P": b"B",  # DOWN
                                     b"M": b"C",  # RIGHT
                                     b"K": b"D",  # LEFT
                                     b"G": b"H",  # POS1
                                     b"O": b"F",  # END
                                     b"Q": b"6~",  # PGDN
                                     b"I": b"5~",  # PGUP
                                     b"s": b"1;5D",  # CTRL-LEFT,
                                     b"t": b"1;5C",  # CTRL-RIGHT,
                                     b"\x8d": b"1;5A",  #  CTRL-UP,
                                     b"\x91": b"1;5B",  # CTRL-DOWN,
                                     b"w" : b"1;5H",  # CTRL-POS1
                                     b"u" : b"1;5F", # CTRL-END
                                     b"\x98": b"1;3A",  #  ALT-UP,
                                     b"\xa0": b"1;3B",  # ALT-DOWN,
                                     b"\x9d": b"1;3C",  #  ALT-RIGHT,
                                     b"\x9b": b"1;3D",  # ALT-LEFT,
                                     b"\x97": b"1;3H",  #  ALT-POS1,
                                     b"\x9f": b"1;3F",  # ALT-END,
                                     b"S" : b"3~",  # DEL,
                                     b"\x93": b"3;5~",  # CTRL-DEL
                                     b"R" : b"2~",  # INS
                                     b"\x92": b"2;5~",  # CTRL-INS
                                     b"\x94" : b"Z",  # Ctrl-Tab = BACKTAB,
                                    }[ch]
                except KeyError:
                    return None
            return ch

    def write(self, buf):
        if isinstance(buf, bytes):
            sys.stdout.buffer.write(buf)
        else:
            sys.stdout.write(buf)
        sys.stdout.flush()
        # for b in buf:
        #     if isinstance(b, bytes):
        #         msvcrt.putch(b)
        #     else:
        #         msvcrt.putwch(b)


if termios:
    Console = ConsolePosix
    VT_ENABLED = True
else:
    Console = ConsoleWindows

    # Windows VT mode ( >= win10 only)
    # https://bugs.python.org/msg291732
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    ERROR_INVALID_PARAMETER = 0x0057
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    def _check_bool(result, func, args):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return args

    LPDWORD = ctypes.POINTER(wintypes.DWORD)
    kernel32.GetConsoleMode.errcheck = _check_bool
    kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, LPDWORD)
    kernel32.SetConsoleMode.errcheck = _check_bool
    kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)

    def set_conout_mode(new_mode, mask=0xFFFFFFFF):
        # don't assume StandardOutput is a console.
        # open CONOUT$ instead
        fdout = os.open("CONOUT$", os.O_RDWR)
        try:
            hout = msvcrt.get_osfhandle(fdout)
            old_mode = wintypes.DWORD()
            kernel32.GetConsoleMode(hout, ctypes.byref(old_mode))
            mode = (new_mode & mask) | (old_mode.value & ~mask)
            kernel32.SetConsoleMode(hout, mode)
            return old_mode.value
        finally:
            os.close(fdout)

    # def enable_vt_mode():
    mode = mask = ENABLE_VIRTUAL_TERMINAL_PROCESSING
    try:
        set_conout_mode(mode, mask)
        VT_ENABLED = True
    except WindowsError as e:
        VT_ENABLED = False


class PyboardCommand:
    def __init__(self, fin, fout, path):
        self.fin = fin
        self.fout = fout
        self.root = path + "/"
        self.data_ilistdir = ["", []]
        self.data_files = []

    def rd_s8(self):
        return struct.unpack("<b", self.fin.read(1))[0]

    def rd_s32(self):
        return struct.unpack("<i", self.fin.read(4))[0]

    def rd_bytes(self):
        n = self.rd_s32()
        return self.fin.read(n)

    def rd_str(self):
        n = self.rd_s32()
        if n == 0:
            return ""
        else:
            return str(self.fin.read(n), "utf8")

    def wr_s8(self, i):
        self.fout.write(struct.pack("<b", i))

    def wr_s32(self, i):
        self.fout.write(struct.pack("<i", i))

    def wr_u32(self, i):
        self.fout.write(struct.pack("<I", i))

    def wr_bytes(self, b):
        self.wr_s32(len(b))
        self.fout.write(b)

    def wr_str(self, s):
        b = bytes(s, "utf8")
        self.wr_s32(len(b))
        self.fout.write(b)

    def log_cmd(self, msg):
        print(f"[{msg}]", end="\r\n")

    def do_stat(self):
        path = self.root + self.rd_str()
        # self.log_cmd(f"stat {path}")
        try:
            stat = os.stat(path)
        except OSError as er:
            self.wr_s8(-abs(er.args[0]))
        else:
            self.wr_s8(0)
            # Note: st_ino would need to be 64-bit if added here
            self.wr_u32(stat.st_mode)
            self.wr_u32(stat.st_size)
            self.wr_u32(int(stat.st_atime))
            self.wr_u32(int(stat.st_mtime))
            self.wr_u32(int(stat.st_ctime))

    def do_ilistdir_start(self):
        path = self.root + self.rd_str()
        self.data_ilistdir[0] = path
        self.data_ilistdir[1] = os.listdir(path)

    def do_ilistdir_next(self):
        if self.data_ilistdir[1]:
            entry = self.data_ilistdir[1].pop(0)
            stat = os.stat(self.data_ilistdir[0] + "/" + entry)
            self.wr_str(entry)
            self.wr_u32(stat.st_mode & 0xC000)
        else:
            self.wr_str("")

    def do_open(self):
        path = self.root + self.rd_str()
        mode = self.rd_str()
        # self.log_cmd(f"open {path} {mode}")
        try:
            f = open(path, mode)
        except OSError as er:
            self.wr_s8(-abs(er.args[0]))
        else:
            is_text = mode.find("b") == -1
            try:
                fd = self.data_files.index(None)
                self.data_files[fd] = (f, is_text)
            except ValueError:
                fd = len(self.data_files)
                self.data_files.append((f, is_text))
            self.wr_s8(fd)

    def do_close(self):
        fd = self.rd_s8()
        # self.log_cmd(f"close {fd}")
        self.data_files[fd][0].close()
        self.data_files[fd] = None

    def do_read(self):
        fd = self.rd_s8()
        n = self.rd_s32()
        buf = self.data_files[fd][0].read(n)
        if self.data_files[fd][1]:
            buf = bytes(buf, "utf8")
        self.wr_bytes(buf)
        # self.log_cmd(f"read {fd} {n} -> {len(buf)}")

    def do_seek(self):
        fd = self.rd_s8()
        n = self.rd_s32()
        # self.log_cmd(f"seek {fd} {n}")
        self.data_files[fd][0].seek(n)
        self.wr_s32(n)

    def do_write(self):
        fd = self.rd_s8()
        buf = self.rd_bytes()
        if self.data_files[fd][1]:
            buf = str(buf, "utf8")
        n = self.data_files[fd][0].write(buf)
        self.wr_s32(n)
        # self.log_cmd(f"write {fd} {len(buf)} -> {n}")

    def do_remove(self):
        path = self.root + self.rd_str()
        # self.log_cmd(f"remove {path}")
        try:
            os.remove(path)
            ret = 0
        except OSError as er:
            ret = -abs(er.args[0])
        self.wr_s32(ret)

    def do_rename(self):
        old = self.root + self.rd_str()
        new = self.root + self.rd_str()
        # self.log_cmd(f"rename {old} {new}")
        try:
            os.rename(old, new)
            ret = 0
        except OSError as er:
            ret = -abs(er.args[0])
        self.wr_s32(ret)

    cmd_table = {
        fs_hook_cmds["CMD_STAT"]: do_stat,
        fs_hook_cmds["CMD_ILISTDIR_START"]: do_ilistdir_start,
        fs_hook_cmds["CMD_ILISTDIR_NEXT"]: do_ilistdir_next,
        fs_hook_cmds["CMD_OPEN"]: do_open,
        fs_hook_cmds["CMD_CLOSE"]: do_close,
        fs_hook_cmds["CMD_READ"]: do_read,
        fs_hook_cmds["CMD_WRITE"]: do_write,
        fs_hook_cmds["CMD_SEEK"]: do_seek,
        fs_hook_cmds["CMD_REMOVE"]: do_remove,
        fs_hook_cmds["CMD_RENAME"]: do_rename,
    }


class SerialIntercept:
    def __init__(self, serial, cmd):
        self.orig_serial = serial
        self.cmd = cmd
        self.buf = b""
        self.orig_serial.timeout = 5.0

    def _check_input(self, blocking):
        if blocking or self.orig_serial.inWaiting() > 0:
            c = self.orig_serial.read(1)
            if c == b"\x18":
                # a special command
                c = self.orig_serial.read(1)[0]
                PyboardCommand.cmd_table[c](self.cmd)
            elif not VT_ENABLED and c == b"\x1b":
                # ESC code, ignore these on windows
                esctype = self.orig_serial.read(1)
                if esctype == b"[":  # CSI
                    while not (0x40 < self.orig_serial.read(1)[0] < 0x7E):
                        # Looking for "final byte" of escape sequence
                        pass
            else:
                self.buf += c

    @property
    def fd(self):
        return self.orig_serial.fd

    def close(self):
        self.orig_serial.close()

    def inWaiting(self):
        self._check_input(False)
        return len(self.buf)

    def read(self, n):
        while len(self.buf) < n:
            self._check_input(True)
        out = self.buf[:n]
        self.buf = self.buf[n:]
        return out

    def write(self, buf):
        self.orig_serial.write(buf)


class PyboardExtended(pyboard.Pyboard):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mounted = False

    def enter_raw_repl_without_soft_reset(self):
        # ctrl-C twice: interrupt any running program
        self.serial.write(b"\r\x03\x03")

        # flush input (without relying on serial.flushInput())
        n = self.serial.inWaiting()
        while n > 0:
            self.serial.read(n)
            n = self.serial.inWaiting()

        # ctrl-A: enter raw REPL
        self.serial.write(b"\r\x01")
        data = self.read_until(1, b"raw REPL; CTRL-B to exit\r\n")
        if not data.endswith(b"raw REPL; CTRL-B to exit\r\n"):
            raise PyboardError("could not enter raw repl")

    def mount_local(self, path, dev_out=None):
        fout = self.serial
        if dev_out is not None:
            try:
                fout = serial.Serial(dev_out)
            except serial.SerialException:
                port = list(serial.tools.list_ports.grep(dev_out))
                if not port:
                    raise
                for p in port:
                    try:
                        fout = serial.Serial(p.device)
                        break
                    except serial.SerialException:
                        pass
        self.mounted = True
        if self.eval('"RemoteFS" in globals()') == b"False":
            self.exec_(fs_hook_code)
        self.exec_("__mount(%s)" % (dev_out is not None))
        self.cmd = PyboardCommand(self.serial, fout, path)
        self.serial = SerialIntercept(self.serial, self.cmd)
        self.dev_out = dev_out

    def soft_reset_with_mount(self, out_callback):
        if not self.mounted:
            self.serial.write(b"\x04")
            return
        self.serial = self.serial.orig_serial
        self.serial.write(b"\x04")
        out_callback(self.serial.read(1))
        n = self.serial.inWaiting()
        while n > 0:
            buf = self.serial.read(n)
            out_callback(buf)
            time.sleep(0.1)
            n = self.serial.inWaiting()
        self.serial.write(b"\x01")
        self.exec_(fs_hook_code)
        self.exec_("__mount(%s)" % (self.dev_out is not None))
        self.exit_raw_repl()
        self.read_until(4, b">>> ")
        self.serial = SerialIntercept(self.serial, self.cmd)

    def umount_local(self):
        if self.mounted:
            self.exec_('os.umount("/remote")')
            self.mounted = False


def do_repl_main_loop(pyb, console_in, console_out_write, file_to_inject):
    while True:
        try:
            if isinstance(console_in, ConsolePosix):
                # TODO pyb.serial might not have fd
                select.select([console_in.infd, pyb.serial.fd], [], [])
            else:
                while not (console_in.inWaiting() or pyb.serial.inWaiting()):
                    time.sleep(0.01)
            c = console_in.readchar()
            if c:
                if c == b"\x1d":  # ctrl-], quit
                    break
                elif c == b"\x04":  # ctrl-D
                    # do a soft reset and reload the filesystem hook
                    pyb.soft_reset_with_mount(console_out_write)
                elif c == b"\x0b":  # ctrl-k, inject script
                    console_out_write(bytes("Injecting %s\r\n" % file_to_inject, "utf8"))
                    pyb.enter_raw_repl_without_soft_reset()
                    with open(file_to_inject, "rb") as f:
                        pyfile = f.read()
                    try:
                        pyb.exec_raw_no_follow(pyfile)
                    except pyboard.PyboardError as er:
                        console_out_write(b"Error:\r\n")
                        console_out_write(er)
                    pyb.exit_raw_repl()
                else:
                    pyb.serial.write(c)

            try:
                n = pyb.serial.inWaiting()
            except OSError as er:
                if er.args[0] == 5:  # IO error, device disappeared
                    print("device disconnected")
                    break

            if n > 0:
                c = pyb.serial.read(1)
                if c is not None:
                    # pass character through to the console
                    oc = ord(c)
                    if oc in (8, 9, 10, 13, 27) or oc >= 32:
                        console_out_write(c)
                    else:
                        console_out_write(b"[%02x]" % ord(c))
        except KeyboardInterrupt:
            pyb.serial.write(b"\x03")


def do_repl(pyb, dev, args):
    if len(args) and args[0] == "--capture":
        args.pop(0)
        capture_file = args.pop(0)
    else:
        capture_file = None

    file_to_inject = args.pop(0) if len(args) else None

    print("Connected to MicroPython at %s" % dev)
    print("Use Ctrl-] to exit this shell")
    if capture_file is not None:
        print('Capturing session to file "%s"' % capture_file)
        capture_file = open(capture_file, "wb")
    if file_to_inject is not None:
        print('Use Ctrl-K to inject file "%s"' % file_to_inject)

    console = Console()
    console.enter()

    def console_out_write(b):
        console.write(b)
        if capture_file is not None:
            capture_file.write(b)

    try:
        do_repl_main_loop(pyb, console, console_out_write, file_to_inject)
    finally:
        console.exit()
        if capture_file is not None:
            capture_file.close()


def execbuffer(pyb, buf):
    try:
        ret, ret_err = pyb.exec_raw(buf, timeout=None, data_consumer=pyboard.stdout_write_bytes)
    except pyboard.PyboardError as er:
        print(er)
        return 1
    except KeyboardInterrupt:
        return 1
    if ret_err:
        pyb.exit_raw_repl()
        pyboard.stdout_write_bytes(ret_err)
        return 1
    return 0


def main():
    args = sys.argv[1:]

    if args and args[0] in device_shortcuts:
        dev = find_serial_device(args.pop(0))
    elif args and args[0] == "connect":
        args.pop(0)
        dev = find_serial_device(args.pop(0))
    else:
        # auto-detect and auto-connect
        dev = find_serial_device(None)

    pyb = PyboardExtended(dev)
    in_raw_repl = False
    did_action = False

    try:
        while args:
            if args[0] in command_aliases:
                alias = command_aliases[args[0]]
                if isinstance(alias, str):
                    alias = alias.split()
                args[0:1] = alias

            cmds = {
                "mount": (True, False, 1),
                "repl": (False, True, 0),
                "eval": (True, True, 1),
                "exec": (True, True, 1),
                "run": (True, True, 1),
                "fs": (True, True, 1),
            }
            cmd = args.pop(0)
            try:
                need_raw_repl, is_action, num_args_min = cmds[cmd]
            except KeyError:
                print(f"mpr: '{cmd}' is not a command")
                return 1

            if need_raw_repl:
                if not in_raw_repl:
                    pyb.enter_raw_repl()
                    in_raw_repl = True
            else:
                if in_raw_repl:
                    pyb.exit_raw_repl()
                    in_raw_repl = False
            if is_action:
                did_action = True
            if len(args) < num_args_min:
                print(f"mpr: '{cmd}' neads at least {num_args_min} argument(s)")

            if cmd == "mount":
                path = args.pop(0)
                pyb.mount_local(path)
                print(f"Local directory {path} is mounted at /remote")
            elif cmd == "exec":
                ret = execbuffer(pyb, args.pop(0))
                if ret:
                    return ret
            elif cmd == "eval":
                ret = execbuffer(pyb, "print(" + args.pop(0) + ")")
                if ret:
                    return ret
            elif cmd == "fs":
                pyboard.filesystem_command(pyb, args)
                args.clear()
            elif cmd == "repl":
                do_repl(pyb, dev, args)
            elif cmd == "run":
                filename = args.pop(0)
                try:
                    with open(filename, "rb") as f:
                        buf = f.read()
                except OSError:
                    print(f"mpr: could not read file '{filename}'")
                    return 1
                ret = execbuffer(pyb, buf)
                if ret:
                    return ret

        if not did_action:
            if in_raw_repl:
                pyb.exit_raw_repl()
                in_raw_repl = False
            do_repl(pyb, dev, args)
    finally:
        if pyb is not None:
            if False and pyb.mounted:
                if not in_raw_repl:
                    pyb.enter_raw_repl_without_soft_reset()
                    in_raw_repl = True
                pyb.umount_local()
            if False and in_raw_repl:
                pyb.exit_raw_repl()
            pyb.close()


if __name__ == "__main__":
    sys.exit(main())
