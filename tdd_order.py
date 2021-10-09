import sys
import socket
import time

def main() :
    if len(sys.argv) != 6 :
        print("Usage:\n\ttdd_order.py <b|s> <contract> <M|L> <price> <amount>")
        return -1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 44444))

    #request_cmd = "<buy or sell>&<contract>&<market or limit>&price&amount"
    #request_cmd = "b&MTX&L&17903&1"
    #request_cmd = "s&TX&M&&3"
    request_cmd = f"{sys.argv[1]}&{sys.argv[2]}&{sys.argv[3]}&{sys.argv[4]}&{sys.argv[5]}"

    s.send(request_cmd.encode())
    result = s.recv(8)
    print(f"result: {result.decode()}");

    s.close()

if __name__ == '__main__':
    sys.exit(main())

