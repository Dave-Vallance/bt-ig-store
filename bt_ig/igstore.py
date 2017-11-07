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

'''
#Dev IG Imports
from ...dev.trading_ig import (IGService, IGStreamService)
from ...dev.trading_ig.lightstreamer import Subscription
'''


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
        ('currency_code', 'GBP'), #The currency code of the account
        ('practice', True),
        ('account_tmout', 10.0),  # account balance refresh timeout
    )

    _ENVPRACTICE = 'DEMO'
    _ENVLIVE = 'LIVE'

    _ORDEREXECS = {
        bt.Order.Market: 'MARKET',
        bt.Order.Limit: 'LIMIT',
        bt.Order.Stop: 'STOP',
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
        self.igapi.create_session()
        #Work with JSON rather than Pandas for better backtrader integration
        self.igapi.return_dataframe = False
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
        return self._cash

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark / threads could still append
        return [x for x in iter(self.notifs.popleft, None)]

    def get_positions(self):
        #TODO - Get postion info from returned object.
        positions = self.igapi.fetch_open_positions()
        return positions['positions']

    def get_value(self):
        return self._value

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

    def order_create(self, order, stopside=None, takeside=None, **kwargs):
        '''
        additional kwargs

        expiry: Sting, default = 'DFB' Other examples could be 'DEC-14'. Check
        the instrument details through IG to find out the correct expiry.

        guaranteed_stop: Bool, default = False. Sets whether or not to use a
        guranteed stop.

        time_in_force: String. Must be either 'GOOD_TILL_CANCELLED' or "GOOD_TILL_DATE"

        good_till_date: Datetime object. Must be provided is "GOOD_TILL_DATE" is set.
        '''
        okwargs = dict()
        okwargs['currency_code'] = self.p.currency_code
        #okwargs['dealReference'] = order.ref
        okwargs['epic'] = order.data._dataname
        #Size must be positive for both buy and sell orders
        okwargs['size'] = abs(order.created.size)
        okwargs['direction'] = 'BUY' if order.isbuy() else 'SELL'
        okwargs['order_type'] = self._ORDEREXECS[order.exectype]
        #TODO FILL_OR_KILL
        #okwargs['timeInForce'] = 'FILL_OR_KILL'
        okwargs['force_open']= "false"

        #Filler - required arguments can update later if Limit order is required
        okwargs['level'] = order.created.price
        okwargs['limit_level'] = None
        okwargs['limit_distance'] = None
        okwargs['stop_level'] = None
        okwargs['stop_distance'] = None
        #Allow users to set the expiry through kwargs
        if 'expiry' in kwargs:
            okwargs['expiry'] = kwargs["expiry"]
        else:
            okwargs['expiry'] = 'DFB'
        #Allow users to set the a guaranteed stop
        #Convert from boolean value to string.
        if 'guaranteed_stop' in kwargs:
            if kwargs['guaranteed_stop'] == True:
                okwargs['guaranteed_stop'] = "true"
            elif kwargs['guaranteed_stop'] == False:
                okwargs['guaranteed_stop'] = "false"
            else:
                raise ValueError('guaranteed_stop must be a boolean value: "{}" '
                'was entered'.format(kwargs['guaranteed_stop']))
        else:
            okwargs['guaranteed_stop'] = "false"

        #Market orders use an 'order_type' keyword. Limit and stop orders use 'type'
        if order.exectype == bt.Order.Market:
            okwargs['quote_id'] = None

        if order.exectype in [bt.Order.Stop, bt.Order.Limit]:

            #Allow passing of a timeInForce kwarg
            if 'time_in_force' in kwargs:
                okwargs['time_in_force'] = kwargs['time_in_force']
                if kwargs['time_in_force'] == 'GOOD_TILL_DATE':
                    if 'good_till_date' in kwargs:
                        #Trading_IG will do a datetime conversion
                        okwargs['good_till_date'] = kwargs['good_till_date']
                    else:
                        raise ValueError('If timeInForce == GOOD_TILL_DATE, a '
                        'goodTillDate datetime kwarg must be provided.')
            else:
                okwargs['time_in_force'] = 'GOOD_TILL_CANCELLED'

        if order.exectype == bt.Order.StopLimit:
            #TODO
            okwargs['lowerBound'] = order.created.pricelimit
            okwargs['upperBound'] = order.created.pricelimit

        if order.exectype == bt.Order.StopTrail:
            #TODO need to figure out how to get the stop distance and increment
            #from the trail amount.
            print('order trail amount: {}'.format(order.trailamount))
            okwargs['stop_distance'] = order.trailamount
            #okwargs['trailingStopIncrement'] = 'TODO!'

        if stopside is not None:
            okwargs['stop_level'] = stopside.price

        if takeside is not None:
            okwargs['limit_level'] = takeside.price

        okwargs.update(**kwargs)  # anything from the user

        self.q_ordercreate.put((order.ref, okwargs,))
        return order

    def order_cancel(self, order):
        self.q_orderclose.put(order.ref)
        return order

    def _t_order_cancel(self):
        while True:
            oref = self.q_orderclose.get()
            if oref is None:
                break

            oid = self._orders.get(oref, None)
            if oid is None:
                continue  # the order is no longer there
            try:
                o = self.igapi.delete_working_order(oid)
            except Exception as e:
                continue  # not cancelled - FIXME: notify

            self.broker._cancel(oref)

    def _t_order_create(self):
        while True:
            msg = self.q_ordercreate.get()
            if msg is None:
                break

            oref, okwargs = msg
            #Check to see if it is a market order or working order.
            #Market orders have an 'order_type' kwarg. Working orders
            #use the 'type' kwarg for setting stop or limit
            if okwargs['order_type'] == 'MARKET':
                try:

                    #NOTE The IG API will confirm the deal automatically with the
                    #create_open_position call. Therefore if no error is returned here
                    #Then it was accepted and open.
                    o = self.igapi.create_open_position(**okwargs)
                except Exception as e:
                    self.put_notification(e)
                    self.broker._reject(oref)
                    return

            else:
                print('Creating Working Order')
                try:
                    o = self.igapi.create_working_order(**okwargs)

                except Exception as e:
                    print(e)
                    self.put_notification(e)
                    self.broker._reject(oref)
                    return



            # Ids are delivered in different fields and all must be fetched to
            # match them (as executions) to the order generated here
            _o = {'dealId': None}
            oids = list()

            oids.append(o['dealId'])

            #print('_t_order_create Deal ID = {}'.format(o['dealId']))
            if o['dealStatus'] == 'REJECTED':
                self.broker._reject(oref)
                self.put_notification(o['reason'])

            if not oids:
                self.broker._reject(oref)
                return

            self._orders[oref] = oids[0]

            #Send the summission notification
            #TODO Shouldn't this come earlier????
            self.broker._submit(oref)

            if okwargs['order_type'] == 'MARKET':
                self.broker._accept(oref)  # taken immediately
                self.broker._fill(oref, o['size'], o['level'], okwargs['order_type'])
            for oid in oids:
                self._ordersrev[oid] = oref  # maps ids to backtrader order

    def streaming_events(self, tmout=None):
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
