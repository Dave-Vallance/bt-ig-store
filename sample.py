import backtrader as bt
from datetime import datetime
import logging
from extensions.stores.ig.igstore import IGStore
from extensions.stores.ig.igdata import IGData


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

        print('{}: O: {} H: {} L: {} C:{}'.format(dt, self.data.open[0],
                        self.data.high[0],self.data.low[0],self.data.close[0]))

#Logging - Uncomment to see ig_trading library logs
#logging.basicConfig(level=logging.DEBUG)

tframes = dict(
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


data = igs.getdata(dataname='CS.D.GBPUSD.TODAY.IP')
#Replay the data in forward test envirnoment so we can act quicker
cerebro.resampledata(data, timeframe=tframes['minutes'], compression=1, name='GBP_USD')

#Add our strategy
cerebro.addstrategy(IGTest)

# Run over everything
cerebro.run()
