import sys
import logging
import socketserver
import threading
import shioaji as sj

def log_init() :
    #logfmt = '%(asctime)s.%(msecs)03d-%(levelname)s-%(message)s'
    #logdatefmt = '%Y/%m/%d %H:%M:%S'
    #logging.basicConfig(level=logging.DEBUG, format=logfmt, datefmt=logdatefmt)

    logfmt = '%(asctime)s-%(levelname)s-%(message)s'
    logging.basicConfig(level=logging.DEBUG, format=logfmt)

    file_handler = logging.FileHandler('ocs.log')
    file_format = logging.Formatter("%(asctime)s-%(levelname)s-%(message)s")
    file_handler.setFormatter(file_format)
    file_handler.setLevel(logging.INFO)

    logging.getLogger('').addHandler(file_handler)

def logD(msg) :
    logging.debug(msg)

def logE(msg) :
    logging.error(msg)

def logW(msg) :
    logging.warning(msg)

def logI(msg) :
    logging.info(msg)

class ApiError(Exception) :
    pass

class sinopac_shioaji_api :
    def __init__ (self) :
        try :
            logD("__init__()")
            self.__api__ = sj.Shioaji(simulation=True)
        except:
            raise ApiEerror("failed to init")

    def login(self) :
        try :
            logD("login()")
            self.__api__.login(person_id="PAPIUSER01",
                    passwd="2222",
                    contracts_cb=print)
            #api.activate_ca(ca_path="/c/your/ca/path/Sinopac.pfx",
            #        ca_passwd="YOUR_CA_PASSWORD",
            #        person_id="Person of this Ca")

            #you can iter api.Contracts object to know contracts info
            #MXFR<1,2> is small TXF, TXFR<1,2> is big TXF
            #for i in self.__api__.Contracts.Futures :
            #    for j in i:
            #        print(j)

        except :
            raise ApiError("failed to login")

    def logout(self) :
        logD("logout()")
        self.__api__.logout()

    def order(self, buysell, contract, market, price, amount) :
        logD(f"order(): {buysell}, {contract}, {market}, {price}, {amount}")

        if market == 'L' and price == '' :
            #print(f"failed to check argument. price can not be zero string if market is Limit")
            raise ApiError

        contract = \
            self.__api__.Contracts.Futures.TXF.TXFR1 if contract == 'T' else self.__api__.Contracts.Futures.MXF.MXFR1
        order = self.__api__.Order( \
                action = sj.constant.Action.Buy if buysell == 'b' else sj.constant.Action.Sell, \
                price = int(price.strip()), \
                quantity = amount, \
                price_type = sj.constant.FuturesPriceType.MKP if market == 'M' else sj.constant.FuturesPriceType.LMT, \
                order_type=sj.constant.FuturesOrderType.ROD, \
                octype=sj.constant.FuturesOCType.Auto, \
                account=self.__api__.futopt_account)
        trade = self.__api__.place_order(contract, order)
        if trade.status.status == sj.constant.Status.Failed :
            #print(f"failed to order. status code: {trade.status.status_code}")
            raise ApiError

class the_request_handler(socketserver.BaseRequestHandler) :
    def the_command_process(self, command_str) :
        try :
            arg_list = command_str.split('&')
            if len(arg_list) != 5 :
                raise ValueError

            self.api_obj.order(arg_list[0],
                    arg_list[1], arg_list[2],
                    arg_list[3], arg_list[4])

            return "ok"

        except (ApiError, ValueError) :
            return "error"

    def setup (self) :
        global api_obj
        self.api_obj = api_obj

    def handle(self) :
        #cur = threading.current_thread()

        while True:
            request_cmd = self.request.recv(1024)

            if len(request_cmd) == 0 :
                logD('client closed connection.')
                self.request.close()
                break

            result = self.the_command_process(request_cmd.decode())
            self.request.send(result.encode())

class the_server(socketserver.ThreadingMixIn, socketserver.TCPServer) :
    pass

api_obj = None
def main() :
    global api_obj

    log_init()

    try:
        api_obj = sinopac_shioaji_api()
        api_obj.login()
    except :
        logE(f"failed to create and login sinopac shioaji api. abort")
        return -1

    server = the_server(("", 44444), the_request_handler)
    logI(f"server start at: {server.server_address}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logE(f"KeyboardInterrupt, exit.")
        server.server_close()
        api_obj.logout()
        return 0;

if __name__ == "__main__" :
    exit(main())

