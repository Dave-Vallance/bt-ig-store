from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from datetime import datetime, timedelta

from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num, num2date
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader.metabase import MetaParams
from . import igstore


class MetaIGData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaIGData, cls).__init__(name, bases, dct)

        # Register with the store
        igstore.IGStore.DataCls = cls

class IGData(with_metaclass(MetaIGData, DataBase)):
    '''
    params:

    '''
    #TODO insert params
    params = (
        ('historical', False),
        ('useask', False),
        ('bidask', True),
        ('reconnections', -1),
        ('qcheck', 5)
    )

    # States for the Finite State Machine in _load
    _ST_FROM, _ST_START, _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(5)

    _store = igstore.IGStore

    def islive(self):
        '''Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated'''
        return True

    def __init__(self, **kwargs):
        self.o = self._store(**kwargs)


    def setenvironment(self, env):
        '''Receives an environment (cerebro) and passes it over to the store it
        belongs to'''
        super(IGData, self).setenvironment(env)
        env.addstore(self.o)

    def start(self):
        '''Starts the IG connecction and gets the real contract and
        contractdetails if it exists'''
        super(IGData, self).start()

        # Create attributes as soon as possible
        self._statelivereconn = False  # if reconnecting in live state
        self._storedmsg = dict()  # keep pending live message (under None)
        self.qlive = queue.Queue()
        self._state = self._ST_OVER

        # Kickstart store and get queue to wait on
        self.o.start(data=self)

        # check if the granularity is supported
        otf = self.o.get_granularity(self._timeframe, self._compression)
        if otf is None:
            self.put_notification(self.NOTSUPPORTED_TF)
            self._state = self._ST_OVER
            return

        self._start_finish()
        self._state = self._ST_START  # initial state for _load
        self._st_start()

        self._reconns = 0

    def _st_start(self, instart=True, tmout=None):
        if self.p.historical:
            self.put_notification(self.DELAYED)
            dtend = None
            if self.todate < float('inf'):
                dtend = self.todate

            dtbegin = None
            if self.fromdate > float('-inf'):
                dtbegin = self.fromdate

            self.qhist = self.o.candles(
                self.p.dataname, dtbegin, dtend,
                self._timeframe, self._compression)

            self._state = self._ST_HISTORBACK
            return True

        # streaming prices returns the same queue the streamer is using.
        self.qlive = self.o.streaming_prices(self.p.dataname, tmout=tmout)

        if self._statelivereconn:
            self.put_notification(self.DELAYED)

        self._state = self._ST_LIVE
        if instart:
            self._reconns = self.p.reconnections

        return True  # no return before - implicit continue

    def stop(self):
        '''Stops and tells the store to stop'''
        super(IGData, self).stop()
        self.o.stop()

    def haslivedata(self):
        return bool(self._storedmsg or self.qlive)  # do not return the objs


    def _load(self):
        '''
        steps

        1 - check if we status live. If so process message
                - Check for error codes in message and change status appropriately
                - Process the message as long as the status is not trying to reconnect
                - Setup a backfill if data is missing.
        2 - If not, is the status set to perform a backfill?

        '''

        if self._state == self._ST_OVER:
            return False

        while True:
            if self._state == self._ST_LIVE:
                try:
                    msg = (self._storedmsg.pop(None, None) or
                           self.qlive.get(timeout=self._qcheck))
                except queue.Empty:
                    return None  # indicate timeout situation

                if msg is None:  # Conn broken during historical/backfilling
                    self.put_notification(self.CONNBROKEN)
                    self.put_notification(self.DISCONNECTED)
                    self._state = self._ST_OVER
                    return False  # failed

                #TODO handle error messages in feed


                #Check for empty data. Sometimes all the fields return None...
                if msg['UTM'] is None:
                    return None

                #self._reconns = self.p.reconnections

                # Process the message according to expected return type
                if not self._statelivereconn:
                    if self._laststatus != self.LIVE:
                        if self.qlive.qsize() <= 1:  # very short live queue
                            self.put_notification(self.LIVE)

                    ret = self._load_tick(msg)
                    if ret:
                        return True

                    # could not load bar ... go and get new one
                    continue

            elif self._state == self._ST_START:
                if not self._st_start(instart=False):
                    self._state = self._ST_OVER
                    return False

            elif self._state == self._ST_HISTORBACK:
                msg = self.qhist.get()
                if msg is None:  # Conn broken during historical/backfilling
                    # Situation not managed. Simply bail out
                    self.put_notification(self.DISCONNECTED)
                    self._state = self._ST_OVER
                    return False  # error management cancelled the queue

                elif 'TODO' in msg:  #TODO check error Error
                    self.put_notification(self.NOTSUBSCRIBED)
                    self.put_notification(self.DISCONNECTED)
                    self._state = self._ST_OVER
                    return False

                if msg:
                    if self._load_history(msg):
                        return True  # loading worked

                    continue  # not loaded ... date may have been seen
                else:
                    # End of histdata
                    if self.p.historical:  # only historical
                        self.put_notification(self.DISCONNECTED)
                        self._state = self._ST_OVER
                        return False  # end of historical
            #TODO
            #   - Check for delays in feed
            #       - put a self.put_notification(self.DELAYED)
            #       - Attempt to fill in missing data
            #   - Setup a backfill of some sort when starting a feed.
            #   - Set Dissonnected status where appropriate.


    def _load_tick(self, msg):
        #print('MSG = {}'.format(msg))
        #print(msg['UTM'])
        dtobj = datetime.utcfromtimestamp(int(msg['UTM']) / 1000)
        dt = date2num(dtobj)

        try:
            vol = int(msg['LTV'])
        except TypeError:
            vol = 0

        #Check for missing Bid quote (Happens sometimes)
        if msg['BID'] == None and msg['OFR']:
            bid = float(msg['OFR'])
            ofr = float(msg['OFR'])
        #Check for missing offer quote (Happens sometimes)
        elif msg['OFR'] == None and msg['BID']:
            bid = float(msg['BID'])
            ofr = float(msg['BID'])
        else:
            bid = float(msg['BID'])
            ofr = float(msg['OFR'])

        if dt <= self.lines.datetime[-1]:
            return False  # time already seen

        # Common fields
        self.lines.datetime[0] = dt
        self.lines.volume[0] = vol
        self.lines.openinterest[0] = 0.0

        # Put the prices into the bar
        #SOMETIME tick can be missing BID or OFFER.... Need to fallback

        tick = ofr if self.p.useask else bid

        self.lines.open[0] = tick
        self.lines.high[0] = tick
        self.lines.low[0] = tick
        self.lines.close[0] = tick
        self.lines.volume[0] = vol
        self.lines.openinterest[0] = 0.0
        return True


    def _load_history(self, msg):
        #TODO
        #print(msg)

        dtobj = datetime.strptime(msg['snapshotTime'], '%Y:%m:%d-%H:%M:%S')
        dt = date2num(dtobj)
        if dt <= self.lines.datetime[-1]:
            return False  # time already seen

        # Common fields
        self.lines.datetime[0] = dt
        self.lines.volume[0] = float(msg['lastTradedVolume'])
        self.lines.openinterest[0] = 0.0

        # Put the prices into the bar
        if self.p.bidask:
            if not self.p.useask:
                self.lines.open[0] = float(msg['openPrice']['bid'])
                self.lines.high[0] = float(msg['highPrice']['bid'])
                self.lines.low[0] = float(msg['lowPrice']['bid'])
                self.lines.close[0] = float(msg['closePrice']['bid'])
            else:
                self.lines.open[0] = float(msg['openPrice']['ask'])
                self.lines.high[0] = float(msg['highPrice']['ask'])
                self.lines.low[0] = float(msg['lowPrice']['ask'])
                self.lines.close[0] = float(msg['closePrice']['ask'])
        else:
            self.lines.open[0] = ((float(msg['openPrice']['ask']) +
                                float(msg['openPrice']['bid'])) / 2)
            self.lines.high[0] = ((float(msg['highPrice']['ask']) +
                                float(msg['highPrice']['bid'])) / 2)
            self.lines.low[0] = ((float(msg['lowPrice']['ask']) +
                                float(msg['lowPrice']['bid'])) / 2)
            self.lines.close[0] = ((float(msg['closePrice']['ask']) +
                                float(msg['closePrice']['bid'])) / 2)

        return True
