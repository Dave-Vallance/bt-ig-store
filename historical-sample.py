import backtrader as bt
from datetime import datetime
import logging
from bt_ig import IGStore
from bt_ig import IGData


api_key = 'INSERT YOUR API KEY'
usr = 'INSERT YOUR USERNAME'
pwd = 'INSERT YOU PASSWORD'
acc = "INSERT YOUR ACC NUM"

class IGTest(bt.Strategy):
    '''
    Simple strat to test IGStore.
    '''

    def __init__(self):
        pass

    def next(self):
        dt = self.datetime.datetime()
        bar = len(self)
        print('{}: O: {} H: {} L: {} C:{}'.format(dt, self.data.open[0],
                        self.data.high[0],self.data.low[0],self.data.close[0]))


    def notify_order(self,order):
        if order.status == order.Rejected:
            print('Order Rejected')

#Logging - Uncomment to see ig_trading library logs
#logging.basicConfig(level=logging.DEBUG)

tframes = dict(
    seconds = bt.TimeFrame.Seconds,
    minutes=bt.TimeFrame.Minutes,
    daily=bt.TimeFrame.Days,
    weekly=bt.TimeFrame.Weeks,
    monthly=bt.TimeFrame.Months)

#Create an instance of cerebro
cerebro = bt.Cerebro()

#Setup IG
igs = IGStore(usr=usr, pwd=pwd, token=api_key, account=sbet)
broker = igs.getbroker()
cerebro.setbroker(broker)

data = igs.getdata(dataname='CS.D.GBPUSD.TODAY.IP', historical=True,
        timeframe=tframes['minutes'], compression=60,
        fromdate=datetime(2017,11,1,8,0), todate=datetime(2017,11,1,12,0)) #Get 10 bars for testing.
#Replay the data in forward test envirnoment so we can act quicker
cerebro.adddata(data, name='GBP_USD')

#Add our strategy
cerebro.addstrategy(IGTest)

# Run over everything
cerebro.run()
