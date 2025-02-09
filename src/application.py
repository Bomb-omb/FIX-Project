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
        self.portfolio = {}
        self.total_volume = 0.0
        self.vwap_data = {"MSFT": {"priceXvol": 0.0, "total_qty": 0, "vwap": 0.0},
                          "AAPL": {"priceXvol": 0.0, "total_qty": 0, "vwap": 0.0},
                          "BAC": {"priceXvol": 0.0, "total_qty": 0, "vwap": 0.0}}

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
            self.log_missing_fields(message, missing_fields)
            return

        elif msgType == fix.MsgType_OrderCancelReject:
            ClOrdID = extract_message_field_value(fix.ClOrdID(), message)
            logger.error(f"Order Cancel Reject received for ClOrdID: {ClOrdID}")
        return

    def onMessage(self, message, sessionID):
        pass

    def genClOrdID(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        return timestamp
    
    def log_missing_fields(self, message, required_fields):
        FIX_FIELD_NAMES = {
            6: "AvgPx",
            14: "CumQty",
            38: "OrderQty",
            40: "OrdType",
            44: "Price",
            151: "LeavesQty"
        }

        field_info = []
        for field in required_fields:
            try:
                #get the tag and name of the field
                tag = field.getTag()
                name = FIX_FIELD_NAMES.get(tag, "Unknown")
                field_info.append(f"{tag}={name}")
            except Exception as e:
                logger.error(f"Error in extracting field info: {e}")
                print(f"Error in extracting field info: {e}")
        
        missing_fields = ", ".join(field_info)
        logger.warning(f"Missing fields in message: {missing_fields}")
    
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

        last_px = extract_message_field_value(fix.LastPx(), message, 'float') or 0.0
        last_qty = extract_message_field_value(fix.LastQty(), message, 'int')
        exec_qty = extract_message_field_value(fix.LastShares(), message, 'int') or 0

        if not symbol:
            return

        if symbol not in self.portfolio:
            self.portfolio[symbol] = {"position": 0, "avg_price": 0.0, "PnL": 0.0, "unrealised_PnL": 0.0}

        if symbol not in self.vwap_data:
            self.vwap_data[symbol] = {"priceXvol": 0.0, "total_qty": 0, "vwap": 0.0}

        if ord_status in [fix.OrdStatus_FILLED, fix.OrdStatus_PARTIALLY_FILLED]:
            if exec_type == fix.ExecType_FILL:
                self.portfolio[symbol]["position"] += exec_qty if side == fix.Side_BUY else -exec_qty
                self.portfolio[symbol]["avg_price"] = (self.portfolio[symbol]["avg_price"] + last_px) / self.portfolio[symbol]["position"]
                if side == fix.Side_SELL:
                    self.portfolio[symbol]["PnL"] += (last_px - price) * exec_qty
                self.portfolio[symbol]["unrealised_PnL"] = (last_px - self.portfolio[symbol]["avg_price"]) * self.portfolio[symbol]["position"]

        prev_cum_qty = self.order_book.get(cl_ord_id, {}).get("cum_qty", 0) or 0

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
                del self.open_orders[cl_ord_id]
            if cl_ord_id in self.order_book:
                del self.order_book[cl_ord_id]
            print(f"Order Cancelled/Rejected: ClOrdID={cl_ord_id}, Symbol={symbol}, Side={side}")
            return

        if exec_type == fix.ExecType_PARTIAL_FILL:
            self.order_book[cl_ord_id] = {"symbol": symbol,
                "side": side,
                "order_qty": order_qty,
                "price": price,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": avg_px
            }

            self.total_volume += last_px * exec_qty

            self.portfolio[cl_ord_id] = {"symbol": symbol, "side": side, "order_qty": order_qty, "price": price, "PnL": 0}

            self.vwap_data[symbol]["priceXvol"] += last_px * exec_qty
            self.vwap_data[symbol]["total_qty"] += exec_qty
            self.vwap_data[symbol]["vwap"] = self.vwap_data[symbol]["priceXvol"] / self.vwap_data[symbol]["total_qty"] if self.vwap_data[symbol]["total_qty"] > 0 else 0.0

        if exec_type == fix.ExecType_FILL:
            self.order_book[cl_ord_id] = {"symbol": symbol,
                "side": side,
                "order_qty": order_qty,
                "price": price,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": avg_px
            }

            self.vwap_data[symbol]["priceXvol"] += last_px * exec_qty
            self.vwap_data[symbol]["total_qty"] += exec_qty
            self.vwap_data[symbol]["vwap"] = self.vwap_data[symbol]["priceXvol"] / self.vwap_data[symbol]["total_qty"] if self.vwap_data[symbol]["total_qty"] > 0 else 0.0

            self.total_volume += last_px * exec_qty

            if cl_ord_id in self.open_orders:
                del self.open_orders[cl_ord_id]

            self.portfolio[cl_ord_id] = {"symbol": symbol, "side": side, "order_qty": order_qty, "price": price}
                
        self.pnl = sum(self.portfolio[symbol].get("PnL", 0.0) for symbol in self.portfolio)
        
        print("\n============ MARKET STATS ============")
        for symbol, data in self.vwap_data.items():
            print(f"VWAP for {symbol}: {round(data['vwap'], 5)} USD")
        print(f"Total Volume: {round(self.total_volume, 5)} USD")
        print(f"PnL: {round(self.pnl, 5)} USD")
        print("======================================\n")

        self.save_market_stats()

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

    def save_market_stats(self):
        with open("market_stats.txt", "w") as f:
            f.write("\n============ MARKET STATS ============\n")
            for symbol, data in self.vwap_data.items():
                f.write(f"VWAP for {symbol}: {round(data['vwap'], 5)} USD\n")
            f.write(f"Total Volume: {round(self.total_volume, 5)} USD\n")
            f.write(f"PnL: {round(self.pnl, 5)} USD\n")
            f.write("======================================\n")

        print("Market stats saved to market_stats.txt")

    def new_order(self):
        symbols = ["MSFT", "AAPL", "BAC"]
        ord_types = [fix.OrdType_LIMIT, fix.OrdType_MARKET]

        ord_type = random.choice(ord_types)
        symbol = random.choice(symbols)
        order_qty = random.randint(1,100)
        price = random.uniform(100,200) if ord_type == fix.OrdType_LIMIT else None

        if symbol in self.portfolio and self.portfolio[symbol]["position"] > 0:
            sides = [fix.Side_SELL, fix.Side_BUY]
        else:
            sides = [fix.Side_BUY, fix.Side_SELL_SHORT]

        side = random.choice(sides)

        if side == fix.Side_SELL and symbol in self.portfolio:
            max_sell_qty = self.portfolio[symbol]["position"]
            if max_sell_qty > 0:
                order_qty = random.randint(1, max_sell_qty)
            else:
                print(f"Cannot sell {symbol} as position is 0")

        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle)) #39 = D 

        ClOrdID = self.genClOrdID()
        message.setField(fix.ClOrdID(ClOrdID)) 
        message.setField(fix.Side(side)) 
        message.setField(fix.Symbol(symbol)) 
        message.setField(fix.OrderQty(order_qty))
        message.setField(fix.OrdType(ord_type))
        if ord_type == fix.OrdType_LIMIT:
            message.setField(fix.Price(price))
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
        self.order_book[ClOrdID] = {"symbol": symbol,
                                    "side": side,
                                    "order_qty": order_qty,
                                    "price": price if ord_type == fix.OrdType_LIMIT else None,
                                    "cum_qty": 0,
                                    "leaves_qty": order_qty,
                                    "avg_px": 0.0
                                    }
        
        self.open_orders[ClOrdID] = self.order_book[ClOrdID].copy()
        print(f"Order {ClOrdID} sent")

    def order_cancel(self, ClOrdID):
        if ClOrdID not in self.open_orders:
            print(f"Invalid ClOrdID: {ClOrdID}")
            return

        original_order = self.open_orders[ClOrdID]
        symbol = original_order["symbol"]
        side = original_order["side"]

        if not symbol or not side:
            print(f"Invalid order details for ClOrdID: {ClOrdID}")
            return

        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))

        message.setField(fix.ClOrdID(self.genClOrdID()))
        message.setField(fix.OrigClOrdID(ClOrdID))
        message.setField(fix.Symbol(symbol))
        message.setField(fix.Side(side))
        message.setField(fix.Text("OrderCancelRequest"))
        trstime = fix.TransactTime()
        trstime.setString(datetime.now().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(trstime)
        message.setField(fix.CxlRejResponseTo("1"))

        raw_msg = message.toString().replace(__SOH__, "|")
        logger.info(f"DEBUG: Sending Order Cancel Request -> {raw_msg}")

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
                if order_count == 1000:
                    logger.info("Order count reached, stopping order window")
                    break


                self.new_order()
                order_count += 1

                if random.random() < 0.1 and self.open_orders:
                    cancel_ID = random.choice(list(self.open_orders.keys()))
                    self.order_cancel(cancel_ID)
                    
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Order window interrupted")
            return
        except Exception as e:
            logger.error("Error in order window: %s" % e)
            return
    
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

