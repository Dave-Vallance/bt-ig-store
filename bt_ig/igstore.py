'''
Dreamworld

#My question about store development
https://community.backtrader.com/topic/459/store-development/2

#Example for adding a data feed. Can use online sources
https://www.backtrader.com/docu/datafeed-develop-general/datafeed-develop-general.html

I need to implement


2) IG Broker - Look at bt/brokers/oandabroker.py for an Example
1) IG Store
1) IG Feed - Look at bt/feeds/oanda.py for an Example. It seems the feed
imports and has many references to the store.

'''

#Python Imports
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
from datetime import datetime, timedelta
import time as _time
import json
import threading


#Backtrader imports
import backtrader as bt
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import queue, with_metaclass
from backtrader.utils import AutoDict

#IG Imports
from trading_ig import (IGService, IGStreamService)
from trading_ig.lightstreamer import Subscription


#TODO ADD Errors if appropriate


class Streamer(IGStreamService):
    '''
    TODO
        - Boatloads!
        - Add a listener for notifiactions
    '''
    def __init__(self, q, *args, **kwargs):
        super(Streamer, self).__init__(*args, **kwargs)

        #q is an actual queue
        self.q = q

    def run(self, params):

        self.connected = True
        #params = params or {}


    def on_prices_update(self, data):
        '''
        Oandapy uses on_success from the api to extract the data feed.

        For IG, we register the on_prices_update listener.
        '''
        self.q.put(data['values'])

    def on_error(self,data):

        # Disconnecting
        ig_stream_service.disconnect()
        #TODO Add error message from data


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton

    MetaParams - Imported from backtrader framework
    '''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class IGStore(with_metaclass(MetaSingleton, object)):
    '''
    The IG store class should inherit from the the metaclass and add some
    extensions to it.
    '''
    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    params = (
        ('token', ''),
        ('account', ''),
        ('usr', ''),
        ('pwd', ''),
        ('practice', True)
    )

    _ENVPRACTICE = 'demo'
    _ENVLIVE = 'live'

    _ORDEREXECS = {
        bt.Order.Market: 'TODO',
        bt.Order.Limit: 'TODO',
        bt.Order.Stop: 'TODO',
        bt.Order.StopLimit: 'TODO',
    }

    _GRANULARITIES = 'TODO - NEEDED FOR HISTORICAL'


    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)


    def __init__(self):
        super(IGStore, self).__init__()

        self.notifs = collections.deque()  # store notifications for cerebro
        self._env = None  # reference to cerebro for general notifications
        self.broker = None  # broker instance
        self.datas = list()  # datas that have registered over start

        self._orders = collections.OrderedDict()  # map order.ref to oid
        self._ordersrev = collections.OrderedDict()  # map oid to order.ref
        self._transpend = collections.defaultdict(collections.deque)

        self._oenv = self._ENVPRACTICE if self.p.practice else self._ENVLIVE

        self.igapi = IGService(self.p.usr, self.p.pwd, self.p.token, self._oenv)
        self._cash = 0.0
        self._value = 0.0
        self._evt_acct = threading.Event()

    def broker_threads(self):
        '''
        Setting up threads and targets for broker related notifications.
        '''
        self.q_account = queue.Queue()
        self.q_account.put(True)  # force an immediate update
        t = threading.Thread(target=self._t_account)
        t.daemon = True
        t.start()

        self.q_ordercreate = queue.Queue()
        t = threading.Thread(target=self._t_order_create)
        t.daemon = True
        t.start()

        self.q_orderclose = queue.Queue()
        t = threading.Thread(target=self._t_order_cancel)
        t.daemon = True
        t.start()

        # Wait once for the values to be set
        self._evt_acct.wait(self.p.account_tmout)

    def get_cash(self):
        #TODO - Check where we
        self._value

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark / threads could still append
        return [x for x in iter(self.notifs.popleft, None)]


    def get_positions(self):
        #TODO - Get postion info from returned object.
        positions = self.igapi.fetch_open_positions()
        return positions

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def start(self, data=None, broker=None):
        # Datas require some processing to kickstart data reception
        if data is None and broker is None:
            self.cash = None
            return

        if data is not None:
            self._env = data._env
            # For datas simulate a queue with None to kickstart co
            self.datas.append(data)

            if self.broker is not None:
                self.broker.data_started(data)

        elif broker is not None:
            self.broker = broker
            self.streaming_events()
            self.broker_threads()

    def stop(self):
        # signal end of thread
        if self.broker is not None:
            self.q_ordercreate.put(None)
            self.q_orderclose.put(None)
            self.q_account.put(None)


    '''
    Loads of methods to add in-between
    '''
    def streaming_prices(self, dataname, tmout=None):
        q = queue.Queue()
        kwargs = {'q': q, 'dataname': dataname, 'tmout': tmout}
        t = threading.Thread(target=self._t_streaming_prices, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q


    def _t_account(self):
        #TODO
        pass

    def _t_order_cancel(self):
        #TODO
        pass

    def _t_order_create(self):
        #TODO
        pass

    def _process_transaction(self, oid, trans):
        #TODO
        pass

    def _t_streaming_prices(self, dataname, q, tmout):
        '''
        Target for the streaming prices thread. This will setup the streamer.
        '''
        if tmout is not None:
            _time.sleep(tmout)

        igss = Streamer(q, ig_service=self.igapi)
        ig_session = igss.create_session()
        igss.connect(self.p.account)

        epic = 'CHART:'+dataname+':TICK'
        # Making a new Subscription in MERGE mode
        subcription_prices = Subscription(
            mode="DISTINCT",
            items=[epic],
            fields=["UTM", "BID", "OFR", "TTV","LTV"],
            )
            #adapter="QUOTE_ADAPTER")

        # Adding the "on_price_update" function to Subscription
        subcription_prices.addlistener(igss.on_prices_update)

        sub_key_prices = igss.ls_client.subscribe(subcription_prices)
