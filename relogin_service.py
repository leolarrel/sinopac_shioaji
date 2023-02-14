import sys
import zmq
import time
import datetime as dt

def send_relogin_command() :
    context = zmq.Context()
    sender = context.socket(zmq.PUSH)
    sender.connect("tcp://127.0.0.1:44444")

    request_cmd = "r&"
    sender.send_string(request_cmd)
    sender.close()

def main() :
    sleep_time = (3 * 60)
    relogin_list = ['14:47:00', '07:00:00']
    relogin_interval = (10 * 60)
    sent = False

    while True :
        matched = False
        __now = int(time.time())
        now_timestamp =  __now % (24 * 60 * 60)

        for relogin_start in relogin_list :
            temp1 = int(dt.datetime.strptime(f"1970-01-03 {relogin_start}", "%Y-%m-%d %H:%M:%S").timestamp())
            relogin_timestamp = temp1 % (24 * 60 * 60)

            if (now_timestamp >= relogin_timestamp and
                now_timestamp < (relogin_timestamp + (relogin_interval))) :
                matched = True
                break

        if matched == True :
            if sent == False :
                sent = send_relogin_command()
        else :
            sent = False

        time.sleep(sleep_time)

if __name__ == '__main__':
    sys.exit(main())

