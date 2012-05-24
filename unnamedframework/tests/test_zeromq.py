from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest
from txzmq import ZmqFactory

from unnamedframework.actor.actor import Actor
from unnamedframework.actor.transport.zeromq import ZmqRouter, ZmqDealer
from unnamedframework.util.async import TimeoutError, sleep, with_timeout
from unnamedframework.util.testing import assert_not_raises


_wait_msg = lambda d: with_timeout(4.0, d)
_wait_slow_joiners = lambda n=1: sleep(0.05 * n)


ADDR = 'ipc://test'


class TestCaseBase(unittest.TestCase):

    def setUp(self):
        self._z_components = []
        self._z_factory = ZmqFactory()

    def _make(self, cls, endpoint, identity=None, with_mock=False):
        ret = cls(self._z_factory, endpoint, identity)
        self._z_components.append(ret)
        if with_mock:
            mocked_inboxes = with_mock
            assert isinstance(mocked_inboxes, (list, basestring, bool))

            if isinstance(mocked_inboxes, bool):
                mocked_inboxes = 'default'

            mock = Actor()
            ret.connect(mocked_inboxes, mock)
            ret = ret, mock
        return ret

    def _make_dealer(self, *args, **kwargs):
        return self._make(ZmqDealer, *args, **kwargs)

    def _make_router(self, *args, **kwargs):
        return self._make(ZmqRouter, *args, **kwargs)

    def tearDown(self):
        for component in self._z_components:
            component.stop()


class RouterDealerTestCase(TestCaseBase):

    @inlineCallbacks
    def _do_test_router_with_n_dealers(self, n):
        router = self._make_router(ADDR)
        dealers = []
        for i in range(n):
            dealer, mock = self._make_dealer(ADDR, identity='dude%s' % i, with_mock=True)
            dealers.append((dealer, mock))
        yield _wait_slow_joiners(n)

        for dealer, mock in dealers:
            msg = 'PING%s' % i

            router.deliver(message=msg, inbox='default', routing_key=dealer.identity)
            with assert_not_raises(TimeoutError, "should have received a message"):
                assert msg == (yield _wait_msg(mock.get('default')))

    def test_router_with_1_dealer(self):
        return self._do_test_router_with_n_dealers(1)

    def test_router_with_2_dealers(self):
        return self._do_test_router_with_n_dealers(2)

    def test_router_with_3_dealers(self):
        return self._do_test_router_with_n_dealers(3)

    def test_router_with_10_dealers(self):
        return self._do_test_router_with_n_dealers(10)
