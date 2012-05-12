from itertools import count

from unnamedframework.component.component import Component


class RoutingException(Exception):
    pass


class InMemRouterEndpoint(Component):

    def __init__(self, manager):
        super(InMemRouterEndpoint, self).__init__()
        self._manager = manager

    def deliver(self, message, inbox, routing_key):
        self._manager._delivered_to_router(message, inbox, routing_key)


class InMemDealerEndpoint(Component):

    identity = property(lambda self: self._identity)

    def __init__(self, manager, identity):
        super(InMemDealerEndpoint, self).__init__()
        self._manager = manager
        self._identity = identity

    def deliver(self, message, inbox, routing_key):
        assert routing_key is None
        self._manager._delivered_to_dealer(self, message, inbox)


class InMemoryRouting(object):

    def __init__(self, id_gen_fn=None):
        self._router_endpoint = None
        self._dealer_endpoints = []
        self._dealer_id_gen_fn = id_gen_fn or count().next
        self._used_deaer_identities = set()

        self._server = None
        self._clients = {}

    def make_router_endpoint(self):
        if self._router_endpoint:
            raise Exception()
        self._router_endpoint = InMemRouterEndpoint(manager=self)
        # directlyProvides(self._router_endpoint, [IProducer, IConsumer])
        return self._router_endpoint

    def make_dealer_endpoint(self, identity=None):
        if identity in self._used_deaer_identities:
            raise Exception()
        identity = self._dealer_id_gen_fn() if identity is None else identity
        self._used_deaer_identities.add(identity)
        ret = InMemDealerEndpoint(manager=self, identity=identity)
        self._dealer_endpoints.append(ret)
        return ret

    def dealer_gone(self, dealer):
        self._dealer_endpoints.remove(dealer)

    def _delivered_to_dealer(self, dealer, message, inbox):
        if dealer not in self._dealer_endpoints:
            raise RoutingException("No such dealer (anymore)")
        self._router_endpoint.put(outbox=inbox, message=(dealer.identity, message))

    def _delivered_to_router(self, message, inbox, routing_key):
        if routing_key is None:
            raise Exception("Routing key must be specified when sending to a router endpoint")
        for dealer in self._dealer_endpoints:
            if dealer.identity == routing_key:
                dealer.put(outbox=inbox, message=message)
                break
        else:
            raise RoutingException("No dealer ID matches the specified routing key")

    def assign_server(self, server, inbox, outbox):
        if self._server:
            raise RoutingException("Can assign only one server")
        self._server = True
        router = self.make_router_endpoint()
        router.connect('default', (inbox, server))
        server.connect(outbox, ('default', router))

    def add_client(self, client, inbox, outbox):
        if client in self._clients:
            raise RoutingException("Attempt add the same client more than once")

        dealer = self.make_dealer_endpoint()

        self._clients[client] = dealer
        client.connect(outbox, ('default', dealer))
        dealer.connect('default', (inbox, client))

    def remove_client(self, client):
        if client not in self._clients:
            raise RoutingException("Attempt to remove a non-existent client")
        self.dealer_gone(self._clients[client])
        del self._clients[client]
