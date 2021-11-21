import sys
import json
import configparser
from datetime import datetime as dt
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
    def __init__ (self, simulate) :
        logD("__init__()")

        try :
            with open("nearby_contract.json", "r") as f:
                temp = json.load(f)

            self.__nearby_contract_list__ = temp["nearby_contract_record"]
            for i in self.__nearby_contract_list__ :
                temp = dt.strptime(i["delivery"], "%Y/%m/%d %H:%M:%S")
                i["timestamp"] = int(temp.timestamp())

            self.simulate = True if simulate == "yes" else False
            self.__api__ = sj.Shioaji(simulation = self.simulate)
            self.__api__.set_order_callback(self.order_callback)

        except Exception as e :
            logE(f"{e}")
            raise ApiEerror("failed to init")

    def order_callback (self, stat, msg) :
        logD("order_callback")
        logI(f'order event occur {dt.now()}\n{stat}\n{msg}\n')

    def login(self, arg_id, arg_passwd, arg_ca_path, arg_ca_passwd) :
        try :
            logD("login()")
            self.__api__.login(person_id = arg_id, \
                               passwd = arg_passwd, \
                               contracts_cb=print)
            if self.simulate == False :
                self.__api__.activate_ca(ca_path = arg_ca_path, \
                                         ca_passwd = arg_ca_passwd, \
                                         person_id = arg_id)

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

    def verify_nearby_contract(self, contract) :
        temp = dt.now().timestamp()
        nearby_contract_name = ""
        for i in self.__nearby_contract_list__ :
            if temp < i["timestamp"] :
                nearby_contract_name = "TXF" if contract == 'T' else "MXF"
                nearby_contract_name += i["month"]
                break

        temp = self.__api__.Contracts.Futures.TXF if contract == 'T' else self.__api__.Contracts.Futures.MXF
        for i in temp :
            if nearby_contract_name == i.symbol :
                return i

        raise ApiError

    def order(self, buysell, contract, market, price, position) :
        logD(f"order(): {buysell},{contract},{market},{price},{position}")

        real_contract = self.verify_nearby_contract(contract)

        order = self.__api__.Order( \
                action = sj.constant.Action.Buy if buysell == 'b' else sj.constant.Action.Sell, \
                price = int(price.strip()), \
                quantity = position, \
                price_type = sj.constant.FuturesPriceType.MKP if market == 'M' else sj.constant.FuturesPriceType.LMT, \
                order_type = sj.constant.FuturesOrderType.IOC if market == 'M' else sj.constant.FuturesOrderType.ROD, \
                octype = sj.constant.FuturesOCType.Auto, \
                account = self.__api__.futopt_account)

        trade = self.__api__.place_order(real_contract, order)
        if trade.status.status == sj.constant.Status.Failed :
            logE(f"failed to order. status code: {trade.status.status_code}")
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
        ini_setting = configparser.ConfigParser()
        ini_setting.read("setting.ini")

        api_obj = sinopac_shioaji_api(ini_setting["global"]["simulation"])
        api_obj.login(ini_setting["global"]["id"], \
                      ini_setting["global"]["password"], \
                      ini_setting["global"]["ca_file"], \
                      ini_setting["global"]["ca_password"])
    except :
        logE(f"failed to create and login sinopac shioaji api. abort")
        return -1

    server = the_server(("", 44444), the_request_handler)
    logI(f"server start at: {server.server_address}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logE(f"KeyboardInterrupt, exit.")

    logD(f"waiting all server thread stop...")
    server.server_close()
    logD(f"all server thread has stopped")
    api_obj.logout()
    return 0;

if __name__ == "__main__" :
    exit(main())

