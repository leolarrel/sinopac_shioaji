import sys
import socket
import time

def main() :
    if (len(sys.argv) != 1) == False :
        print("Usage:\n\ttdd_order.py f <b|s> <contract> <M|L> <price> <amount>")
        print("Usage:\n\ttdd_order.py o <b|s> <contract> <contract_price> <C|P> <M|L> <price> <amount>")
        print("Usage:\n\ttdd_order.py r")
        return -1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 44444))

    request_cmd = ""
    if sys.argv[1] == "r" :
        request_cmd = "r&"
    else :
        #futures:
        #request_cmd = "<buy or sell>&<contract>&<market or limit>&price&amount"
        #request_cmd = "b&MXF&L&17903&1" #buy MXF limit 17903 one contract
        #request_cmd = "s&TXF&M&0&3" #sell TXF market three contract
        #Options:
        #request_cmd = "<buy or sell>&<contract>&<contract_price>&<call or put>&<market or limit>&price&amount"
        #request_cmd = "b&TXF&14500&C&L&45.0&1" #buy TXF 14500 call limit 45.0 one contract
        #request_cmd = "s&TXF&12000&P&M&0&3" #sell TXF 12000 put market three contract

        __temp = sys.argv[1:]
        for i in __temp :
            request_cmd += f"{i}&"
        request_cmd = request_cmd[:-1]
        print(request_cmd)

    s.send(request_cmd.encode())
    result = s.recv(8)
    print(f"result: {result.decode()}");

    s.close()

if __name__ == '__main__':
    sys.exit(main())

