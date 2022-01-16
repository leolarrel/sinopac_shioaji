import sys
import socket
import time
import datetime as dt

def send_relogin_command() :
    try :
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 44444))

        request_cmd = "r&"
        s.send(request_cmd.encode())
        result = s.recv(8)

        s.close()

    except ConnectionRefusedError as e :
        print(e)
        result = b'failed'

    print(f"send relogin: result: {result.decode()}");

def main() :
    sleep_time = 1 * 60
    relogin_start = '07:20:00'
    relogin_interval = (2 * 60 * 60)
    flag = False

    while True :
        temp1 = int(dt.datetime.strptime(f"1970-01-03 {relogin_start}",
                                         "%Y-%m-%d %H:%M:%S").timestamp())
        temp2 = int(time.time())

        relogin_timestamp = temp1 % (24 * 60 * 60)
        now_timestamp = temp2 % (24 * 60 * 60)

        if (now_timestamp > relogin_timestamp and
            now_timestamp < (relogin_timestamp + (relogin_interval))) :
            if flag == False :
                send_relogin_command()
                flag = True
        else :
                flag = False

        time.sleep(sleep_time)

if __name__ == '__main__':
    sys.exit(main())

