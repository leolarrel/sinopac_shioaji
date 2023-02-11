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
        self.account_akey = None
        self.account_skey = None

        self.contract_fetch_O = False
        self.contract_fetch_I = False
        self.contract_fetch_S = False
        self.contract_fetch_F = False
        self.__future_contract_db__ = {}
        self.__option_contract_db__ = {}
        self.__tx_option_delivery__ = None

        self.api_lock = threading.Lock()

    def order_callback (self, stat, msg) :
        logD("order_callback")

        if stat == sj.constant.OrderState.FuturesOrder :
            logI(f"Order: {msg['operation']}")
        elif stat == sj.constant.OrderState.FuturesDeal :
            logI(f'Deal: {msg}')

    def rebuild_contract_db(self, a) :
        #you can for loop api.Contracts object to know contracts info
        #MXFR<1,2> is small TXF, TXFR<1,2> is big TXF
        #for i in self.__api__.Contracts.Futures :
        #    for j in i:
        #        print(j)

        b = str(a)

        if "Index" in b:
            self.contract_fetch_I = True
        elif "Stock" in b:
            self.contract_fetch_S = True
        elif "Future" in b :
            self.contract_fetch_F = True
        elif "Option" in b:
            self.contract_fetch_O = True

        if not (self.contract_fetch_I == True and
            self.contract_fetch_S == True and
            self.contract_fetch_F == True and
            self.contract_fetch_O == True) :
            return

        logI("rebuild_contract_db(): build future database")
        for i in self.__api__.Contracts.Futures :
            l = [j for j in i if j.code[-2:] not in ["R1", "R2"]]
            l.sort(key=lambda t: t.delivery_date)
            self.__future_contract_db__[l[0].category] = l

        logI("rebuild_contract_db(): build option database")
        __dict1 = {}
        for n in self.__api__.Contracts.Options :
            #__category = str(n)[0:3]
            __delivery_date = {t.delivery_date for t in n}

            __dict2 = {}
            for nn in __delivery_date :
                __lst = [t for t in n if t.delivery_date == nn]
                if len(__lst) == 0 :
                    continue

                __lst.sort(key=lambda t: t.symbol)
                __dict2[dt.strptime(f"{nn} 13:29:00", "%Y/%m/%d %H:%M:%S")] = tuple(__lst)
                __category = __lst[0].category

            self.__option_contract_db__[__category] = __dict2
            if "TX" in __category :
                temp = sorted(__delivery_date)
                __dict1[dt.strptime(f"{temp[0]} 13:29:00", "%Y/%m/%d %H:%M:%S")] = __category

        self.__tx_option_delivery__ = tuple(sorted(__dict1.items()))

    def login(self) :
        logD("login()")
        try :
            self.__api__.login(api_key = self.account_akey,
                               secret_key = self.account_skey,
                               contracts_cb = self.rebuild_contract_db)
            if self.simulate == False :
                self.__api__.activate_ca(ca_path = self.account_ca_path,
                                         ca_passwd = self.account_ca_passwd,
                                         person_id = self.account_id)

        except :
            raise ApiError("failed to login")

    def logout(self) :
        logD("logout()")
        self.__api__.logout()
        self.contract_fetch_O = False
        self.contract_fetch_I = False
        self.contract_fetch_S = False
        self.contract_fetch_F = False
        self.__future_contract_db__ = {}
        self.__option_contract_db__ = {}
        self.__tx_option_delivery__ = None

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

        if __category in self.__future_contract_db__ :
            __found = None
            for i in self.__future_contract_db__[__category] :
                __time_dt = dt.strptime(f"{i.delivery_date} 13:29:00",
                                        "%Y/%m/%d %H:%M:%S")
                __now = dt.today()
                if __now >= __time_dt :
                    continue
                else :
                    __found = i
                    break

            if __found != None :
                return __found

        logE('This message should never be displayed. If you see this message, please debug')

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
        order = self.__api__.Order(action = "Buy" if buysell == 'b' else "Sell",
                                   price = int(price.strip()),
                                   quantity = position,
                                   price_type = "MKP" if market == 'M' else "LMT",
                                   order_type = "IOC" if market == 'M' else "ROD",
                                   octype = "Auto",
                                   account = self.__api__.futopt_account)

        trade = self.__api__.place_order(real_contract, order)
        self.api_lock.release()

        if trade.status.status == sj.constant.Status.Failed :
            raise OrderContractError(f"failed to order. status code: {trade.status.status_code}")

    def __bisect_search_options_contract__(self, __option_tuple, symbol) :
        low = 0
        high = len(__option_tuple) - 1
        mid = 0
        mid_element= None

        while low <= high :
            mid = (high + low) // 2
            mid_element = __option_tuple[mid]

            if mid_element.symbol == symbol :
                return mid_element
            elif mid_element.symbol > symbol :
                high = mid - 1
            elif mid_element.symbol < symbol :
                low = mid + 1

        return None

    def __get_nearby_options_contract__(self, category, call_put, step) :
        __category = category
        __now_time = dt.today()

        if category == "TX" :
            for i in self.__tx_option_delivery__ :
                if __now_time < i[0] :
                    __category = i[1]
                    break

        if __category not in self.__option_contract_db__.keys() :
            raise OrderContractError(f"found not any category name is match '{__category}'")

        __lst = list(self.__option_contract_db__[__category].keys())
        __lst.sort()
        for __delivery_date in __lst :
            if __now_time < __delivery_date :
                break

        __symbol = f"{__category}{__delivery_date.strftime('%Y%m')}{step.zfill(5)}{call_put}"

        __options = self.__option_contract_db__[__category][__delivery_date]
        __found = self.__bisect_search_options_contract__(__options, __symbol)
        if __found != None :
            return __found

        logE('found not option contract, use for loop to try again')

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
        if "TX" not in contract :
            raise OrderContractError("current we just support TX contract")

        real_contract = self.__get_nearby_options_contract__(contract, call_put, contract_price)

        self.api_lock.acquire()
        order = self.__api__.Order(action = "Buy" if buysell == 'b' else "Sell",
                                   price = int(price.strip()),
                                   quantity = position,
                                   price_type = "MKP" if market == 'M' else "LMT",
                                   order_type = "IOC" if market == 'M' else "ROD",
                                   octype = "Auto",
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
        api_obj.account_akey = ini_setting["global"]["api_key"]
        api_obj.account_skey = ini_setting["global"]["secret_key"]
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

