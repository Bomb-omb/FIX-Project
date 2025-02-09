import sys
import quickfix as fix
import time
import logging
from datetime import datetime
from model.logger import setup_logger
import random
import argparse
from helper import extract_message_field_value
from execution_report import execution_report
__SOH__ = chr(1)

#setup logger
setup_logger('logger', 'log/message.log')
logger = logging.getLogger('logger')

class Application(fix.Application):
    def __init__(self):
        super().__init__()
        self.ClOrdID = 0
        self.order_count = 0
        self.open_orders = {}
        self.sessionID = None
        self.order_book = {}
        self.vwap_data = {"MSFT": {"total_value": 0, "total_qty": 0},
                          "AAPL": {"total_value": 0, "total_qty": 0},
                          "BAC": {"total_value": 0, "total_qty": 0}}

    def onCreate(self, sessionID):
        sessionID = sessionID
        print("onCreate : Session (%s)" % sessionID.toString())
        return

    def onLogon(self, sessionID):
        self.sessionID = sessionID
        print("Successful Logon to session '%s'." % sessionID.toString())
        return

    def onLogout(self, sessionID):
        print("Session (%s) logout !" % sessionID.toString())
        return

    def toAdmin(self, message, sessionID):
        msg = message.toString().replace(__SOH__, "|")
        logger.info("(Server) S >> %s" % msg)
        return
    def fromAdmin(self, message, sessionID):
        msg = message.toString().replace(__SOH__, "|")
        logger.info("(Server) R << %s" % msg)
        return
    def toApp(self, message, sessionID):
        msg = message.toString().replace(__SOH__, "|")
        logger.info("(Client) S >> %s" % msg)
        return
    def fromApp(self, message, sessionID):
        msg = message.toString().replace(__SOH__, "|")
        logger.info("(Client) R << %s" % msg)
        self.onMessage(message, sessionID)
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)

        sending_time = extract_message_field_value(fix.SendingTime(), message, 'datetime')

        if msgType.getValue() == fix.MsgType_ExecutionReport:
            self.parse_ExecutionReport(message, sessionID)

        required_fields = [fix.Side(),
                           fix.Symbol(),
                           fix.OrderQty(),
                           fix.OrdType(),
                           fix.Price(),
                           fix.AvgPx(),
                           fix.ExecType(),
                           fix.LeavesQty(),
                           fix.CumQty(),
                           fix.OrderID()]
        
        missing_fields = [name for name in required_fields if not message.isSetField(name)]
        if missing_fields:
            logger.error(f"Missing fields in message: {missing_fields}")
            print(f"Missing fields in message: {missing_fields}")
            return

        elif msgType == fix.MsgType_OrderCancelReject:
            ClOrdID = extract_message_field_value(fix.ClOrdID(), message)
            logger.error(f"Order Cancel Reject received for ClOrdID: {ClOrdID}")
        return

    def onMessage(self, message, sessionID):
        """Processing application message here"""
        pass

    def genClOrdID(self):
        """Generate ClOrdID"""
        """self.ClOrdID += 1
        return str(self.ClOrdID).zfill(5)"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        return timestamp
    
    def parse_ExecutionReport(self, message, sessionID):
        raw_message = message.toString().replace(__SOH__, "|")
        print(f"Debug: {raw_message}")
        exec_type = extract_message_field_value(fix.ExecType(), message, 'str')
        cl_ord_id = extract_message_field_value(fix.ClOrdID(), message, 'str')
        order_id = extract_message_field_value(fix.OrderID(), message, 'str')
        symbol = extract_message_field_value(fix.Symbol(), message, 'str')
        side = extract_message_field_value(fix.Side(), message, 'str')
        order_qty = extract_message_field_value(fix.OrderQty(), message, 'int') or 0
        price = extract_message_field_value(fix.Price(), message, 'float') or 0.0 
        ord_status = extract_message_field_value(fix.OrdStatus(), message, 'str')
        OrdType = extract_message_field_value(fix.OrdType(), message, 'str')
        MinQty = extract_message_field_value(fix.MinQty(), message, 'int')

        last_px = extract_message_field_value(fix.LastPx(), message, 'float')
        last_qty = extract_message_field_value(fix.LastQty(), message, 'int')

        prev_cum_qty = self.order_book.get(cl_ord_id, {}).get("cum_qty", 0)

        if last_px is not None and last_qty is not None:
            cum_qty = prev_cum_qty + last_qty
            leaves_qty = max(0, order_qty - cum_qty)

            prev_avg_px = self.order_book.get(cl_ord_id, {}).get("avg_px", 0) or 0
            avg_px = ((prev_cum_qty * prev_avg_px) + (last_qty * last_px)) / cum_qty if cum_qty > 0 else price
        else:
            cum_qty = prev_cum_qty 
            leaves_qty = max(0, order_qty - cum_qty)
            avg_px = self.order_book.get(cl_ord_id, {}).get("avg_px", price)

        if ord_status not in [fix.OrdStatus_PARTIALLY_FILLED, fix.OrdStatus_FILLED]:
            print(f"skipping execution report with status {ord_status}")
            return

        exec_report = execution_report(exec_type, cl_ord_id, order_id,
                                      symbol, side, order_qty, price, 
                                      avg_px, leaves_qty, cum_qty, 
                                      OrdType, ord_status, MinQty
                                      )
        logger.info(exec_report)

        if ord_status in [fix.OrdStatus_NEW, fix.OrdStatus_PENDING_NEW]:
            print(f"New Order Acknowledged: ClOrdID={cl_ord_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}")
            return  # Don't process stats for `39=0` but display in logs
        
        if ord_status in [fix.OrdStatus_CANCELED, fix.OrdStatus_REJECTED]:
            if cl_ord_id in self.open_orders:
                self.open_orders.remove(cl_ord_id)
            if cl_ord_id in self.order_book:
                del self.order_book[cl_ord_id]
            print(f"Order Cancelled/Rejected: ClOrdID={cl_ord_id}, Symbol={symbol}, Side={side}")
            return

        if exec_type == fix.ExecType_PARTIAL_FILL:
            self.order_book[order_id] = {"symbol": symbol,
                "side": side,
                "order_qty": order_qty,
                "price": price,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": avg_px
            }

        if exec_type == fix.ExecType_FILL:
            self.order_book[order_id] = {"symbol": symbol,
                "side": side,
                "order_qty": order_qty,
                "price": price,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": avg_px
            }
            if cl_ord_id in self.open_orders:
                self.open_orders.remove(cl_ord_id)
                
        self.compute_stats()

        if exec_type == fix.ExecType_NEW:
            logger.info(f"New Order: ClOrdID={cl_ord_id}, OrderID={order_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}")
        elif exec_type == fix.ExecType_FILL:
            logger.info(f"Fill Order: ClOrdID={cl_ord_id}, OrderID={order_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}, AvgPx={avg_px}, LeavesQty={leaves_qty}, CumQty={cum_qty}")
        elif exec_type == fix.ExecType_PARTIAL_FILL:
            logger.info(f"Partial Fill Order: ClOrdID={cl_ord_id}, OrderID={order_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}, AvgPx={avg_px}, LeavesQty={leaves_qty}, CumQty={cum_qty}")
        elif exec_type == fix.ExecType_REJECTED:
            logger.error(f"Order Rejected: ClOrdID={cl_ord_id}, OrderID={order_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}")
        elif exec_type == fix.ExecType_CANCELED:
            logger.info(f"Order Cancelled: ClOrdID={cl_ord_id}, OrderID={order_id}, Symbol={symbol}, Side={side}, OrderQty={order_qty}, Price={price}")
        else:
            logger.error(f"Unknown Execution Type: {exec_type}")

        print("\n===== ORDER BOOK UPDATE =====")
        for clordid, order in self.order_book.items():
            print(f"ClOrdID: {clordid}, Order: {order}")
        print("================================\n")

        print("\n===== OPEN ORDERS =====")
        print(self.open_orders)
        print("========================\n")

    def new_order(self):
        symbols = ["MSFT", "AAPL", "BAC"]
        sides = [fix.Side_BUY, fix.Side_SELL]
        ord_types = [fix.OrdType_LIMIT, fix.OrdType_MARKET]

        ord_type = random.choice(ord_types)

        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle)) #39 = D 

        ClOrdID = self.genClOrdID()
        message.setField(fix.ClOrdID(ClOrdID)) 
        message.setField(fix.Side(random.choice(sides))) 
        message.setField(fix.Symbol(random.choice(symbols))) 
        message.setField(fix.OrderQty(random.randint(1,100)))
        message.setField(fix.OrdType(ord_type))
        if ord_type == fix.OrdType_LIMIT:
            message.setField(fix.Price(random.uniform(100,200)))
        message.setField(fix.HandlInst("1"))
        message.setField(fix.TimeInForce('0'))
        message.setField(fix.Text("NewOrderSingle"))
        trstime = fix.TransactTime()
        trstime.setString(datetime.now().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(trstime)

        raw_msg = message.toString().replace(__SOH__, "|")
        logger.info(f"DEBUG: Sending New Order -> {raw_msg}")

        fix.Session.sendToTarget(message, self.sessionID)

        # Add details to open orders
        self.order_book[ClOrdID] = {"symbol": message.getField(fix.Symbol()).getString(),
                                    "side": message.getField(fix.Side()).getString(),
                                    "order_qty": int(message.getField(fix.OrderQty()).getString()),
                                    "price": float(message.getField(fix.Price()).getString()) if ord_type == fix.OrdType_LIMIT else None,
                                    "cum_qty": 0,
                                    "leaves_qty": int(message.getField(fix.OrderQty()).getString()),
                                    "avg_px": 0
                                    }
        
        self.open_orders[ClOrdID] = self.order_book[ClOrdID].copy()
        print(f"Order {ClOrdID} sent")

    def order_cancel(self, ClOrdID):
        if ClOrdID not in self.open_orders:
            print(f"Invalid ClOrdID: {ClOrdID}")
            return

        original_order = self.open_orders[ClOrdID]
        symbol = original_order.get("symbol")
        side = original_order.get("side")
        order_qty = original_order.get("order_qty")

        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))

        message.setField(fix.ClOrdID(self.genClOrdID()))
        message.setField(fix.OrigClOrdID(ClOrdID))
        message.setField(fix.Symbol(symbol))
        message.setField(fix.Side(side))
        message.setField(fix.OrderQty(order_qty))

        fix.Session.sendToTarget(message, self.sessionID)

        print(f"Order Cancel Request sent for ClOrdID: {ClOrdID}")

    def order_window(self):
        start_time = time.time()
        order_count = 0

        while self.sessionID is None:
            print("Waiting for session to be established")
            time.sleep(1)

        try:
            while time.time() - start_time < 300:
                if order_count == 25:
                    logger.info("Order count reached, stopping order window")
                    break


                self.new_order()
                order_count += 1

                if random.random() < 0.1 and self.open_orders:
                    cancel_ID = random.choice(self.open_orders)
                    self.order_cancel(cancel_ID)
                    
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Order window interrupted")
            return
        except Exception as e:
            logger.error("Error in order window: %s" % e)
            return
        
    def compute_stats(self):
        self.total_volume =sum((order["cum_qty"] or 0) * (order["avg_px"] or 0) for order in self.order_book.values())

        #PnL calculation
        self.pnl = sum((order["cum_qty"] or 0) * ((order["avg_px"] or 0) - (order["price"] or 0)) for order in self.order_book.values())

        #VWAP calculation
        for symbol in ["MSFT", "AAPL", "BAC"]:
            total_value = sum((order["cum_qty"] or 0) * (order["avg_px"] or 0) for order in self.order_book.values() if order["symbol"] == symbol)
            total_qty = sum((order["cum_qty"] or 0) for order in self.order_book.values() if order["symbol"] == symbol)
            self.vwap_data[symbol]["total_value"] = total_value
            self.vwap_data[symbol]["total_qty"] = total_qty

            # Fix division by zero error
            vwap = total_value/total_qty if total_qty > 0 else 0
            print(f"VWAP for {symbol}: {round(vwap, 5)} USD")

        print(f"Total Volume: {round(self.total_volume, 5)} USD")
        print(f"PnL: {round(self.pnl, 5)} USD")
    
def main(config_file):
    try:
        settings = fix.SessionSettings(config_file)
        application = Application(settings)
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
        
        initiator.start()
        application.order_window()
        initiator.stop()

    except (fix.ConfigError, fix.RuntimeError) as e:
        print(e)
        initiator.stop()
        sys.exit()
        while True:
            pass
    
if __name__=='__main__':
    parser = argparse.ArgumentParser(description='FIX Client')
    parser.add_argument('file_name', type=str, help='Name of configuration file')
    args = parser.parse_args()

    try:
        settings = fix.SessionSettings(args.file_name)
        application = Application()
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
            
        initiator.start()
        application.order_window()
        initiator.stop()

    except (fix.ConfigError, fix.RuntimeError) as e:
        print(e)
        initiator.stop()
        sys.exit()
        while True:
            pass

