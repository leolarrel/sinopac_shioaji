import sys
import zmq
import time

def main() :
    if (len(sys.argv) != 1) == False :
        print("Usage:\n\ttdd_order.py f <b|s> <contract> <M|L> <price> <amount>")
        print("Usage:\n\ttdd_order.py o <b|s> <contract> <contract_price> <C|P> <M|L> <price> <amount>")
        print("Usage:\n\ttdd_order.py r")
        print("Usage:\n\ttdd_order.py e")
        return -1

    context = zmq.Context()
    sender = context.socket(zmq.PUSH)
    sender.connect("tcp://127.0.0.1:44444")

    request_cmd = ""
    if sys.argv[1] == "r" :
        request_cmd = "r&"
    elif sys.argv[1] == "e" :
        request_cmd = "e&"
    else :
        #futures:
        #request_cmd = "<future>&<buy or sell>&<contract>&<market or limit>&price&amount"
        #request_cmd = "f&b&MXF&L&17903&1" #buy MXF limit 17903 one contract
        #request_cmd = "f&s&TXF&M&0&3" #sell TXF market three contract
        #Options:
        #request_cmd = "<option>&<buy or sell>&<contract>&<contract_price>&<call or put>&<market or limit>&price&amount"
        #request_cmd = "o&b&TX&14500&C&L&45.0&1" #buy TXF 14500Call limit 45.0 one contract
        #request_cmd = "o&s&TX&12000&P&M&0&3" #sell TXF 12000Put market three contract

        __temp = sys.argv[1:]
        for i in __temp :
            request_cmd += f"{i}&"
        request_cmd = request_cmd[:-1]
        print(f"<{request_cmd}>")

    sender.send_string(request_cmd)
    sender.close()

if __name__ == '__main__':
    sys.exit(main())

