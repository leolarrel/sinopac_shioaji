import sys
import time
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

    logfmt = '%(asctime)s <%(levelname)s> %(message)s'
    logging.basicConfig(level=logging.INFO, format=logfmt)

    file_handler = logging.FileHandler('ocs.log')
    file_format = logging.Formatter("%(asctime)s <%(levelname)s> %(message)s")
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

class OrderContractError(Exception) :
    pass

class sinopac_shioaji_api :
    def __init__ (self, simulate) :
        logD("__init__()")

        self.simulate = True if simulate == "yes" else False
        try :
            self.__api__ = sj.Shioaji(simulation = self.simulate)
        except Exception as e :
            raise ApiEerror("failed to init")

        self.__api__.set_order_callback(self.order_callback)

        self.account_id = None
        self.account_passwd = None
        self.account_ca_path = None
        self.account_ca_passwd = None
        self.api_lock = threading.Lock()

    def order_callback (self, stat, msg) :
        logD("order_callback")
        if stat == sj.constant.OrderState.FOrder :
            op_type = msg["operation"]["op_type"]
            logI(f"Order: {op_type}")
        elif stat == sj.constant.OrderState.FDeal :
            logI(f'Deal\n{msg}')

    def login(self) :
        logD("login()")
        try :
            self.__api__.login(person_id = self.account_id, \
                               passwd = self.account_passwd, \
                               contracts_cb=print)
            if self.simulate == False :
                self.__api__.activate_ca(ca_path = self.account_ca_path, \
                                         ca_passwd = self.account_ca_passwd, \
                                         person_id = self.account_id)

        except :
            raise ApiError("failed to login")

        #you can for loop api.Contracts object to know contracts info
        #MXFR<1,2> is small TXF, TXFR<1,2> is big TXF
        #for i in self.__api__.Contracts.Futures :
        #    for j in i:
        #        print(j)

    def logout(self) :
        logD("logout()")
        self.__api__.logout()

    def relogin(self) :
        logI("relogin")
        self.logout()
        time.sleep(5)
        self.login()

    def __get_nearby_future_contract__(self, category) :
        if category == 'T' : #backport T is TXF
            __category = 'TXF'
        elif category == 'M' : #backport M is MXF
            __category = 'MXF'
        else :
            __category = category

        __flist = {}
        for f in self.__api__.Contracts.Futures :
            for i in f :
                if i.category != __category :
                    continue

                if 'R1' in i.code or 'R2' in i.code :
                    continue

                __time_str = f"{i.delivery_date} 13:25:00"
                __time_stamp = dt.strptime(__time_str, "%Y/%m/%d %H:%M:%S")
                __flist[__time_stamp] = i.code

            if __flist :
                break

        if not __flist :
            #found not any contract
            raise OrderContractError(f"found not any category name is match '{category}'")

        __temp = sorted(__flist.keys())
        __now = dt.today()
        ret = None
        for i in __temp :
            if __now < i :
                __code = __flist[i]
                ret = self.__api__.Contracts.Futures[__code]
                break

        if ret == None :
            #found not any contract
            raise OrderContractError("found not contract {__code}")

        return ret

    def order_futures(self, buysell, contract, market, price, position) :
        logI(f"order_futures() {buysell},{contract},{market},{price},{position}")

        real_contract = self.__get_nearby_future_contract__(contract)

        self.api_lock.acquire()
        order = self.__api__.Order( \
                action = sj.constant.Action.Buy if buysell == 'b' else sj.constant.Action.Sell, \
                price = int(price.strip()), \
                quantity = position, \
                price_type = sj.constant.FuturesPriceType.MKP if market == 'M' else sj.constant.FuturesPriceType.LMT, \
                order_type = sj.constant.FuturesOrderType.IOC if market == 'M' else sj.constant.FuturesOrderType.ROD, \
                octype = sj.constant.FuturesOCType.Auto, \
                account = self.__api__.futopt_account)

        trade = self.__api__.place_order(real_contract, order)
        self.api_lock.release()

        if trade.status.status == sj.constant.Status.Failed :
            raise OrderContractError(f"failed to order. status code: {trade.status.status_code}")

    def __get_nearby_options_contract__(self, category, call_put, step) :
        __odict = {}
        __temp_dict = {}
        for o in self.__api__.Contracts.Options :
            for i in o :
                if category != i.category[:2] :
                    continue

                if i.delivery_date not in __temp_dict.keys() :
                    __temp_dict[i.delivery_date] = f"{i.delivery_month}{i.category}"

        if not __temp_dict :
            raise OrderContractError(f"found not any category name is match '{category}'")

        for i in __temp_dict.keys() :
            __time_stamp = dt.strptime(f"{i} 13:25:00", "%Y/%m/%d %H:%M:%S")
            __odict[__time_stamp] = __temp_dict[i]

        __sort = sorted(__odict.keys())
        __now = dt.today()
        __nearby = None
        for i in __sort:
            if __now < i :
                __nearby = __odict[i]
                break

        if __nearby == None :
            raise OrderContractError("found not any nearby contract")

        __month1 = int(__nearby[4:6])
        __month1 += (ord('A') - 1)
        if call_put == 'P' :
            __month1 += 12
        __month2 = chr(__month1)

        __year1 = int(__nearby[:4])
        __year1 -= 2020

        __step = f"0000{step}"
        __step = __step[-5:]
        __code = f"{__nearby[-3:]}{__step}{__month2}{__year1}"

        ret = self.__api__.Contracts.Options[__code]
        if ret == None :
            #found not any contract
            raise OrderContractError(f"found not contract {__code}")

        return ret

    def order_options(self, buysell, contract, contract_price, call_put, market, price, position) :
        logI(f"order_options() {buysell},{contract},{contract_price},{call_put},{market},{price},{position}")

        #current we just support TX contract.
        if contract != "TX" :
            raise OrderContractError("current we just support TX contract")

        real_contract = self.__get_nearby_options_contract__(contract, call_put, contract_price)

        self.api_lock.acquire()
        order = self.__api__.Order( \
                action = sj.constant.Action.Buy if buysell == 'b' else sj.constant.Action.Sell, \
                price = int(price.strip()), \
                quantity = position, \
                price_type = sj.constant.FuturesPriceType.MKP if market == 'M' else sj.constant.FuturesPriceType.LMT, \
                order_type = sj.constant.FuturesOrderType.IOC if market == 'M' else sj.constant.FuturesOrderType.ROD, \
                octype = sj.constant.FuturesOCType.Auto, \
                account = self.__api__.futopt_account)

        trade = self.__api__.place_order(real_contract, order)
        self.api_lock.release()

        if trade.status.status == sj.constant.Status.Failed :
            raise OrderContractError(f"failed to order. status code: {trade.status.status_code}")

class the_request_handler(socketserver.BaseRequestHandler) :
    def remote_command_process(self, command_str) :
        ret = "ok"
        try :
            arg_list = command_str.split('&')
            if arg_list[0] == 'r' :
                self.api_obj.relogin()

            elif arg_list[0] == 'f' : #futures
                if len(arg_list) != 6 :
                    raise TypeError("The number of arguments for ordering Future is incorrect")

                self.api_obj.order_futures(arg_list[1],
                                           arg_list[2],
                                           arg_list[3],
                                           arg_list[4],
                                           arg_list[5])

            elif arg_list[0] == 'o' : #Options
                if len(arg_list) != 8 :
                    raise TypeError("The number of arguments for ordering Option is incorrect")

                self.api_obj.order_options(arg_list[1],
                                           arg_list[2],
                                           arg_list[3],
                                           arg_list[4],
                                           arg_list[5],
                                           arg_list[6],
                                           arg_list[7])

#            elif arg_list[0] == 's' : #stocks
#                ret = "error"
            else :
                raise TypeError("Not support")


        except Exception as e :
            logE(f"remote_command_process(): {type(e).__name__}: {e}")
            ret = "error"

        return ret

    def setup (self) :
        global api_obj
        self.api_obj = api_obj

    def handle(self) :
        #cur = threading.current_thread()
        logD('client connect')

        while True:
            request_cmd = self.request.recv(1024)

            if len(request_cmd) == 0 :
                logD('client closed connection.')
                self.request.close()
                break

            result = self.remote_command_process(request_cmd.decode())
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
        api_obj.account_id = ini_setting["global"]["id"]
        api_obj.account_passwd = ini_setting["global"]["password"]
        api_obj.account_ca_path = ini_setting["global"]["ca_file"]
        api_obj.account_ca_passwd = ini_setting["global"]["ca_password"]
        api_obj.login()

    except Exception as e :
        logE(f"main(): {type(e).__name__}: {e}: program abort.")
        return -1

    server = the_server(("", 44444), the_request_handler)
    logI(f"server start at: {server.server_address}")

    try:
        server.serve_forever()
    except KeyboardInterrupt :
        logI(f"main(): KeyboardInterrupt, program quit.")
    except Exception as e :
        logE(f"main(): {type(e).__name__}: {e}: program abort.")

    logD(f"waiting all server thread stop...")
    server.server_close()
    logD(f"all server thread has stopped")
    api_obj.logout()
    return 0;

if __name__ == "__main__" :
    exit(main())

