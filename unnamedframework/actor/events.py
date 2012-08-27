from __future__ import print_function

import sys
import traceback
from collections import namedtuple

from twisted.internet.defer import Deferred


def fields(*args):
    return namedtuple('_', args)


class Event(object):
    def __repr__(self):
        return '%s(%s)' % (type(self).__name__, self.repr_args())

    def repr_args(self):
        return '%r' % (self.actor,)


class MessageReceived(Event, fields('actor', 'message')):
    def repr_args(self):
        return (super(MessageReceived, self).repr_args() +
                ', message=%r' % (self.message,))


class UnhandledMessage(MessageReceived, fields('actor')):
    pass


class DeadLetter(Event, fields('actor', 'message')):
    def repr_args(self):
        return (super(DeadLetter, self).repr_args() + (', %r' % (self.message, )))


class LifecycleEvent(Event):
    pass


class LifecycleWarning(Event, fields('actor', 'message')):
    def repr_args(self):
        return super(LifecycleWarning, self).repr_args() + (', %r' % (self.message,))


class Started(LifecycleEvent, fields('actor')):
    pass


class Error(LifecycleEvent, fields('actor', 'exc', 'tb')):
    """Logged by actors as they run into errors.

    This is done before the error is reported to the supervisor so even handled errors are logged this way.

    """
    def repr_args(self):
        try:
            formatted_traceback = '\n' + traceback.format_exception(self.exc, None, self.tb)
        except Exception:
            formatted_traceback = ', %r, %r' % (self.exc, self.tb)  # to support passing pattern matchers as event args
        return super(Error, self).repr_args() + formatted_traceback


class UnhandledError(Error, fields('actor', 'exc', 'tb')):
    """Logged by the System actor in the case of errors coming from top-level actors."""


class ErrorIgnored(Error, fields('actor', 'exc', 'tb')):
    """Logged whenever there is an exception in an actor but this exception cannot be reported.

    The causes for this event is either an exception in Actor.post_stop or an exception when the actor is being
    stopped anyway.

    """


class SupervisionFailure(Error, fields('actor', 'exc', 'tb')):
    """Logged when reporting an exception fails (due to what might be a bug in the framework)."""


class _SupressedBase(LifecycleEvent):
    """Internal base class that implements the logic shared by the Suspended and Terminated events."""
    def __new__(cls, actor, reason=None):
        return super(_SupressedBase, cls).__new__(cls, actor, reason)

    def repr_args(self):
        return (super(_SupressedBase, self).repr_args() +
                (', reason=%r' % (self.reason, ) if self.reason else ''))


class Suspended(_SupressedBase, fields('actor', 'reason')):
    pass


class Resumed(LifecycleEvent, fields('actor')):
    pass


class Terminated(_SupressedBase, fields('actor', 'reason')):
    pass


class TopLevelActorTerminated(Terminated, fields('actor', 'reason')):
    pass


class HighWaterMarkReached(Event, fields('actor', 'count')):
    pass


class Events(object):
    # TODO: add {event type} + {actor / actor path} based subscriptions.

    LOGFILE = sys.stdout
    ERRFILE = LOGFILE

    subscriptions = {}
    consumers = {}

    def log(self, event):
        consumers = self.consumers.get(type(event))
        if consumers:
            consumer_d = consumers.pop(0)
            consumer_d.callback(event)
            return

        subscriptions = self.subscriptions.get(type(event))
        if subscriptions:
            for fn in subscriptions:
                try:
                    fn(event)
                except Exception:
                    print("Error in event handler:", file=sys.stderr)
                    traceback.print_exc()
        else:
            print("*** %r" % (event,), file=self.ERRFILE if isinstance(event, Error) else self.LOGFILE)

    def subscribe(self, event_type, fn):
        self.subscriptions.setdefault(event_type, []).append(fn)

    def unsubscribe(self, event_type, fn):
        subscribers = self.subscriptions.get(event_type, [])
        if fn in subscribers:
            subscribers.remove(fn)

    def consume_one(self, event_type):
        assert isinstance(event_type, type)
        c = self.consumers
        d = Deferred(lambda _: c[event_type].remove(d))
        c.setdefault(event_type, []).append(d)
        return d

    def reset(self):
        self.subscriptions = {}
        self.consumers = {}
Events = Events()


def test_basic():
    assert repr(MessageReceived('SomeActor@/foo/bar', 'some-message')) == \
        "MessageReceived('SomeActor@/foo/bar', message='some-message')"
    assert repr(UnhandledMessage('SomeActor@/foo/bar', 'some-message')) == \
        "UnhandledMessage('SomeActor@/foo/bar', message='some-message')"

    assert repr(Started('SomeActor@/foo/bar')) == \
        "Started('SomeActor@/foo/bar')"

    assert repr(Suspended('SomeActor@/foo/bar')) == \
        "Suspended('SomeActor@/foo/bar')"
    assert repr(Suspended('SomeActor@/foo/bar', Exception('message'))) == \
        "Suspended('SomeActor@/foo/bar', reason=Exception('message',))"

    assert repr(Resumed('SomeActor@/foo/bar')) == \
        "Resumed('SomeActor@/foo/bar')"

    assert repr(Terminated('SomeActor@/foo/bar')) == \
        "Terminated('SomeActor@/foo/bar')"
    assert repr(Terminated('SomeActor@/foo/bar', Exception('message'))) == \
        "Terminated('SomeActor@/foo/bar', reason=Exception('message',))"


def test_equality():
    assert UnhandledMessage('SomeActor@/foo/bar', 'some-message') == UnhandledMessage('SomeActor@/foo/bar', 'some-message')


def test_subscribe_and_unsubscribe():
    errors = []
    Events.subscribe(UnhandledError, errors.append)
    Events.log(UnhandledError('actor', 1, 2))
    assert errors == [UnhandledError('actor', 1, 2)]

    errors[:] = []
    Events.unsubscribe(UnhandledError, errors.append)
    event = UnhandledError('actor', 1, 2)
    Events.log(event)
    assert errors == []