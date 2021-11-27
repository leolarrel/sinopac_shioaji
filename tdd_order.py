import sys
import socket
import time

def main() :
    if (len(sys.argv) != 1 and (sys.argv[1] == 'r' or ((sys.argv[1] == 'b' or sys.argv[1] == 's') and len(sys.argv) == 6))) == False :
        print("Usage:\n\ttdd_order.py <b|s> <contract> <M|L> <price> <amount>")
        print("Usage:\n\ttdd_order.py r")
        return -1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 44444))

    if sys.argv[1] == "r" :
        request_cmd = "r&"
    else :
        #request_cmd = "<buy or sell>&<contract>&<market or limit>&price&amount"
        #request_cmd = "b&M&L&17903&1" #buy MTX limit 17903 one contract
        #request_cmd = "s&T&M&0&3" #sell TX market three contract
        request_cmd = f"{sys.argv[1]}&{sys.argv[2]}&{sys.argv[3]}&{sys.argv[4]}&{sys.argv[5]}"

    s.send(request_cmd.encode())
    result = s.recv(8)
    print(f"result: {result.decode()}");

    s.close()

if __name__ == '__main__':
    sys.exit(main())

