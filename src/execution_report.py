class execution_report():
    
    # Side: 1=buy, 2=sell, 5=sell short
    def __init__(self, exec_type, ClOrdID, OrdID, Symbol, Side, 
                 OrderQty, Price, AvgPx, LeavesQty, CumQty,
                 OrdType, OrdStatus, MinQty,):

        self.ExecType = exec_type
        self.ClOrdID = ClOrdID
        self.OrdID = OrdID
        self.Symbol = Symbol
        self.Side = Side
        self.Price = Price
        self.OrdType = OrdType
        self.OrdStatus = OrdStatus
        self.OrderQty = OrderQty
        self.MinQty = MinQty
        self.CumQty = CumQty
        self.LeavesQty = LeavesQty
        self.AvgPx = AvgPx

    def __str__(self):
        return (f"Execution Report: {self.ExecType} {self.OrdStatus} {self.Symbol} {self.Side} {self.OrderQty} {self.Price} {self.AvgPx} {self.LeavesQty} {self.CumQty} {self.OrdType} {self.MinQty}")