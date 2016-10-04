import socket
import network
import os
from time import localtime
month_name = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def send_list_data(cwd, dataclient):
    for file in os.listdir(cwd):
        stat = os.stat(get_absolute_path(cwd, file))
        file_permissions = "drwxr-xr-x" if (stat[0] & 0o170000 == 0o040000) else "-rw-r--r--"
        file_size = stat[6]
        tm = localtime(stat[7])
        if tm[0] != localtime()[0]:
            description = "{}    1 owner group {:>10} {} {:2} {:>5} {}\r\n".format(
                file_permissions, file_size, month_name[tm[1]], tm[2], tm[0], file)
        else:
            description = "{}    1 owner group {:>10} {} {:2} {:02}:{:02} {}\r\n".format(
                file_permissions, file_size, month_name[tm[1]], tm[2], tm[3], tm[4], file)
        dataclient.sendall(description)
        
def send_file_data(path, dataclient):
    with open(path) as file:
        chunk = file.read(128)
        while len(chunk) > 0:
            dataclient.sendall(chunk)
            chunk = file.read(128)

def save_file_data(path, dataclient):
    with open(path, "w") as file:
        chunk = dataclient.read(128)
        while len(chunk) > 0:
            file.write(chunk)
            chunk = dataclient.read(128)

def get_absolute_path(cwd, payload):
    # if it doesn't start with / consider
    # it a relative path
    if not payload.startswith("/"):
        payload = cwd + "/" + payload
    # and don't leave any trailing /
    return payload.rstrip("/")

def ftpserver():

    DATA_PORT = 13333

    ftpsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    datasocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    ftpsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    datasocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    ftpsocket.bind(socket.getaddrinfo("0.0.0.0", 21)[0][4])
    datasocket.bind(socket.getaddrinfo("0.0.0.0", DATA_PORT)[0][4])

    ftpsocket.listen(1)
    datasocket.listen(1)
    datasocket.settimeout(10)

    dataclient = None

    try:
        dataclient = None
        trying = True
        while trying:
            cwd = "/"
            cl, remote_addr = ftpsocket.accept()
            cl.settimeout(300)
            try:
                print("FTP connection from:", remote_addr)
                cl.sendall("220 Hello, this is the ESP8266.\r\n")
                while True:
                    data = cl.readline().decode("utf-8").replace("\r\n", "")
                    if len(data) <= 0:
                        print("Client is dead")
                        # trying = False
                        break
                    
                    command, payload =  (data.split(" ") + [""])[:2]
                    command = command.upper()
                    
                    print("Command={}, Payload={}".format(command, payload))
                    
                    if command == "USER":
                        cl.sendall("230 Logged in.\r\n")
                    elif command == "SYST":
                        cl.sendall("215 ESP8266 MicroPython\r\n")
                    elif command == "NOOP":
                        cl.sendall("200 OK\r\n")
                    elif command == "PWD":
                        cl.sendall('257 "{}"\r\n'.format(cwd))
                    elif command == "CWD":
                        path = get_absolute_path(cwd, payload)
                        try:
                            files = os.listdir(path)
                            cwd = path
                            cl.sendall('250 Directory changed successfully\r\n')
                        except:
                            cl.sendall('550 Failed to change directory\r\n')
                    elif command == "EPSV":
                        cl.sendall('502\r\n')
                    elif command == "TYPE":
                        # probably should switch between binary and not
                        cl.sendall('200 Transfer mode set\r\n')
                    elif command == "SIZE":
                        path = get_absolute_path(cwd, payload)
                        try:
                            size = os.stat(path)[6]
                            cl.sendall('213 {}\r\n'.format(size))
                        except:
                            cl.sendall('550 Could not get file size\r\n')
                    elif command == "QUIT":
                        cl.sendall('221 Bye.\r\n')
                    elif command == "PASV":
                        addr = network.WLAN().ifconfig()[0]
                        cl.sendall('227 Entering Passive Mode ({},{},{}).\r\n'.format(addr.replace('.',','), DATA_PORT>>8, DATA_PORT%256))
                        dataclient, data_addr = datasocket.accept()
                        print("FTP Data connection from:", data_addr)
                    elif command == "LIST":
                        try:
                            send_list_data(cwd, dataclient)
                            dataclient.close()
                            cl.sendall("150 Here comes the directory listing.\r\n")
                            cl.sendall("226 Listed.\r\n")
                        except:
                            cl.sendall('550 Failed to list directory\r\n')
                        finally:
                            dataclient.close()
                    elif command == "RETR":
                        try:
                            send_file_data(get_absolute_path(cwd, payload), dataclient)
                            dataclient.close()
                            cl.sendall("150 Opening data connection.\r\n")
                            cl.sendall("226 Transfer complete.\r\n")
                        except:
                            cl.sendall('550 Failed to send file\r\n')
                        finally:
                            dataclient.close()
                    elif command == "STOR":
                        try:
                            cl.sendall("150 Ok to send data.\r\n")
                            save_file_data(get_absolute_path(cwd, payload), dataclient)
                            dataclient.close()
                            cl.sendall("226 Transfer complete.\r\n")
                        except:
                            cl.sendall('550 Failed to send file\r\n')
                        finally:
                            dataclient.close()
                    elif command == "DELE" or command == "RMD":
                        try:
                            os.remove(get_absolute_path(cwd, payload))
                            cl.sendall("250 Object deleted.\r\n")
                        except:
                            cl.sendall('550 Failed to delete\r\n')
                    elif command == "MKD":
                        try:
                            os.mkdir(payload)
                            cl.sendall("250 Directory created.\r\n")
                        except:
                            cl.sendall('550 Failed to create\r\n')
                    else:
                        cl.sendall("502 Unsupported command.\r\n")
                        print("Unsupported command {} with payload {}".format(command, payload))
                        
            finally:
                cl.close()
    finally:
        datasocket.close()
        ftpsocket.close()
        if dataclient is not None:
            dataclient.close()
            
ftpserver()
