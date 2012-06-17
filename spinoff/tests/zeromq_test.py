from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest
from txzmq import ZmqFactory

from spinoff.actor.transport.zeromq import ZmqRouter, ZmqDealer
from spinoff.util.async import TimeoutError, sleep, with_timeout
from spinoff.util.testing import assert_not_raises, MockActor


_wait_msg = lambda d: with_timeout(4.0, d)
_wait_slow_joiners = lambda n=1: sleep(0.05 * n)


ADDR = 'ipc://test'


class TestCaseBase(unittest.TestCase):

    def setUp(self):
        self._z_components = []
        self._z_factory = ZmqFactory()

    def _make(self, cls, endpoint, identity=None, with_mock=False):
        if with_mock:
            mock = MockActor.spawn()
            ret = mock.spawn(cls, self._z_factory, endpoint, identity)
            ret.connect(mock)
            self._z_components.append(ret)
            ret = ret, mock
        else:
            ret = cls.spawn(self._z_factory, endpoint, identity)
            self._z_components.append(ret)
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

            router.send(message=(dealer.identity, msg))
            with assert_not_raises(TimeoutError, "should have received a message"):
                assert msg == (yield mock.wait())

    def test_router_with_1_dealer(self):
        return self._do_test_router_with_n_dealers(1)

    def test_router_with_2_dealers(self):
        return self._do_test_router_with_n_dealers(2)

    def test_router_with_3_dealers(self):
        return self._do_test_router_with_n_dealers(3)

    def test_router_with_10_dealers(self):
        return self._do_test_router_with_n_dealers(10)
