# bt-ig-store

IG markets store for Backtrader

## Warning UNDER Development
Currently integration is very limited. Only streaming is working.  

__Requires__

1 - trading_ig

A lightweight Python library that can be used to get live data from IG Markets REST and STREAM API

- https://github.com/ig-python/ig-markets-api-python-library

2 - Backtrader

Python Backtesting library for trading strategies
- https://github.com/mementum/backtrader
- https://www.backtrader.com

3 - Pandas.

- http://pandas.pydata.org/


## Current Functionality

- __*basic*__ instrument streaming
- __*New:*__ IG Broker: Performs the open position check when initialized to track existing positions
- __*New:*__ Opening and closing of simple Market orders using the self.buy() and self.close() is now supported.
- __*New:*__ Set IG currency code as a store initialization parameter (Default GBP).

##Known Issues

On my MAC i get a 'fund mode' attribute error from the broker observer when running cerebro.
Oddly enough on my Windows work machine, this does not happen. If you try to run the store
and get a similar error, cerebro needs to be initialized with `stdstats=false` for now until I fix it.

## Streaming Example

```python
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
```
