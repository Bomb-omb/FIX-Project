# FIXversion: 4.2
# Language: Python 3.9

import sys
import os
import argparse
import quickfix as fix
import quickfix42 as fix42
import logging, random
import time
from datetime import datetime

class Application(fix.Application):

    def __init__(self):
        super(Application, self).__init__()
        self.logger  = logging.getLogger(self.__class__.__name__)
        self.sessionID = None
        self.connected = False

    def onCreate(self, sessionID):
        self.sessionID = sessionID
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{sessionID.toString()}")
        self.logger.info(f"Session created: {sessionID}")
    
    def onLogon(self, sessionID):
        self.logger.info(f"Logon: {sessionID}")
        self.connected = True
        print(f"Logon: {sessionID}")
    
    def onLogout(self, sessionID):
        self.logger.info(f"Logout: {sessionID}")
        self.connected = False
        print(f"Logout: {sessionID}")
    
    def toAdmin(self, message, sessionID):
        self.logger.info(f"{self._client_str} {sessionID} {message}")
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)
    
    def fromAdmin(self, message, sessionID):
        self.logger.info(f"{self._server_str} {sessionID} {message}")

    def toApp(self, message, sessionID):
        self.logger.info(f"{self._client_str} {sessionID} {message}")
    
    def fromApp(self, message, sessionID):
        self.logger.info(f"{self._server_str} {sessionID} {message}")
        """
        price = fix.Price()
        message.getField(price)

        clOrdID = fix.ClOrdID()
        message.getField(clOrdID)"""

    def getSettings(self):
        return self.session_settings

    def orderGeneratorandSender(self):
        if self.sessionID is None:
            print("No session ID found")
            return
        
        tickers = ["MSFT", "AAPL", "BAC"]
        sides = [fix.Side_BUY, fix.Side_SELL, fix.Side_SELL_SHORT]

        ticker = random.choice(tickers)
        side = random.choice(sides)
        order_type = random.choice([fix.OrdType_LIMIT, fix.OrdType_MARKET])
        price = random.uniform(100, 200) if order_type == fix.OrdType_LIMIT else None
        quantity = random.randint(1, 1000)

        order_id = str(random.randint(1, 100000))

        # Creating new order single message
        message = fix42.NewOrderSingle()
        header = message.getHeader()
        header.setField(fix.BeginString("FIX.4.2"))
        sender_comp_id = self.session_settings.get(self.sessionID).getString("SenderCompID")
        target_comp_id = self.session_settings.get(self.sessionID).getString("TargetCompID")
        header.setField(fix.SenderCompID(sender_comp_id))
        header.setField(fix.TargetCompID(target_comp_id))
        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))

        # Set order fields
        message.setField(fix.ClOrdID(order_id))
        message.setField(fix.Symbol(ticker))
        message.setField(fix.Side(side))
        message.setField(fix.OrderQty(quantity))
        message.setField(fix.OrdType(order_type))

        if price:
            message.setField(fix.Price(price))

        try:
            fix.Session.sendToTarget(message, self.sessionID)
            print(f"Sent {side} order for {quantity} {ticker} at {price if price else 'market'}")
            return order_id
        except fix.SessionNotFound:
            print("Session not found")
            return 

    def cancelOrder(self, order_id):
        if self.sessionID is None:
            print("No session ID found")
            return
        
        message = fix42.OrderCancelRequest()
        header = message.getHeader()
        header.setField(fix.BeginString("FIX.4.2"))
        sender_comp_id = self.session_settings.get(self.sessionID).getString("SenderCompID")
        target_comp_id = self.session_settings.get(self.sessionID).getString("TargetCompID")
        header.setField(fix.SenderCompID(sender_comp_id))
        header.setField(fix.TargetCompID(target_comp_id))
        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))

        ticker = random.choice(["MSFT", "AAPL", "BAC"])
        side = random.choice([fix.Side_BUY, fix.Side_SELL, fix.Side_SELL_SHORT])

        message.setField(fix.OrigClOrdID(order_id))
        message.setField(fix.ClOrdID(str(random.randint(1, 100000))))
        message.setField(fix.Symbol(ticker))
        message.setField(fix.Side(side))

        fix.Session.sendToTarget(message, self.sessionID)
        print(f"Sent cancel order for {order_id}")

        try:
            fix.Session.sendToTarget(message, self.sessionID)
            print(f"Sent cancel order for {order_id}")
        except fix.SessionNotFound:
            print("Session not found")

    def sendOrderWindow(self):
        start_time = time.time()
        orders = []

        try:
            while time.time() - start_time < 300: # 5-minute window
                if len(orders) < 1000:
                    order_id = self.orderGeneratorandSender()
                    if order_id:
                        orders.append(order_id) # track order IDs

                if random.random() < 0.1 and orders:
                    cancel_id = random.choice(orders)
                    self.cancelOrder(order_id=cancel_id)
                    if cancel_id in orders:
                        orders.remove(cancel_id)

                time.sleep(0.1)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2: 
        print("Usage: client.py <config_file>")
        sys.exit(1)

    configFileName = sys.argv[1]

    if not os.path.exists(configFileName):
            print(f"Configuration File {configFileName} not found")
            sys.exit(1)

    try:
        settings = fix.SessionSettings(configFileName)
        application = Application()
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
        
        initiator.start()
        
        print("FIX client started")    
        application.sendOrderWindow()
    except KeyboardInterrupt:
        print("Shutting down FIX client")
        initiator.stop()
    except fix.ConfigError as e:
        print(f"ConfigError: {e}")
        sys.exit()