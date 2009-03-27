"""
This module provides Pyglet/Twisted integration using
the new (Pyglet v1.1) pyglet.app event loop.

To use this reactor, include the following statements
_before_ importing the standard Twisted reactor:

    import pygletreactor
    pygletreactor.install()

Then, just import reactor and call run() to start both
Pyglet and Twisted:

    from twisted.internet import reactor
    reactor.run()

There is no need to call pyglet.app.run().

If you want to subclass pyglet.app.EventLoop (Pyglet 1.1)
or pyglet.app.base.EventLoop (Pyglet 1.1.2), don't! Subclass
pygletreactor.EventLoop instead, which contains logic
to schedule Twisted events to run from Pyglet. Then,
register your new event loop as follows:

    from twisted.internet import reactor
    reactor.registerPygletEventLoop(yourEventLoop)
    reactor.run()

Twisted function calls are scheduled within the Pyglet event
loop. By default, pending calls are dealt with every 0.1 secs.
This frequency can be altered by passing a different 'call_interval'
to reactor.run(), e.g. the following:

	reactor.run(call_interval=1/20.)

will result in Twisted function calls being dealt with every
0.05 secs within the Pyglet event loop. If your code results in
a large number of Twisted calls that need to be processed as
quickly as possible, decreasing the call_interval will help.

Based on the wxPython reactor (wxreactor.py) that ships with Twisted.

Padraig Kitterick <p.kitterick@psych.york.ac.uk>
"""

import Queue

import pyglet

from twisted.python import log, runtime
from twisted.internet import _threadedselect

try:
    # Pyglet 1.1.2
    from pyglet.app.base import EventLoop
    pyglet_event_loop = pyglet.app.base.EventLoop
except ImportError:
    # Pyglet 1.1
    pyglet_event_loop = pyglet.app.EventLoop

class EventLoop(pyglet_event_loop):

    def __init__(self, twisted_queue=None, call_interval=1/10.):
        """Set up extra cruft to integrate Twisted calls."""

        pyglet_event_loop.__init__(self)
        
        if not hasattr(self, "clock"):
            # This is not defined in Pyglet 1.1
            self.clock = pyglet.clock.get_default()

        if not twisted_queue is None:
            self.register_twisted_queue(twisted_queue, call_interval)        

    def register_twisted_queue(self, twisted_queue, call_interval):
        # The queue containing Twisted function references to call
        self._twisted_call_queue = twisted_queue
        
        # Schedule a method to deal with Twisted calls
        self.clock.schedule_interval_soft(self._make_twisted_calls, call_interval)

    def _make_twisted_calls(self, dt):
        """Check if we need to make function calls for Twisted."""
        
        try:
            # Deal with the next function call in the queue
            f = self._twisted_call_queue.get(False)
            f()
        except Queue.Empty:
            pass

class PygletReactor(_threadedselect.ThreadedSelectReactor):
    """
    Pyglet reactor.

    Twisted events are integrated into the Pyglet event loop.
    """

    _stopping = False

    def registerPygletEventLoop(self, eventloop):
        """Register the pygletreactor.EventLoop instance
        if necessary, i.e. if you need to subclass it.
        """
        
        self.pygletEventLoop = eventloop
    
    def stop(self):
        """Stop Twisted."""
        
        if self._stopping:
            return
        self._stopping = True
        _threadedselect.ThreadedSelectReactor.stop(self)

    def _runInMainThread(self, f):
        """Schedule Twisted calls within the Pyglet event loop."""
        
        if hasattr(self, "pygletEventLoop"):
            # Add the function to a queue which is called as part
            # of the Pyglet event loop (see EventLoop above)
            self._twistedQueue.put(f)
        else:
            # If Pyglet has stopped, add the events to a queue which
            # is processed prior to shutting Twisted down.
            self._postQueue.put(f)

    def _stopPyglet(self):
        """Stop the pyglet event loop."""
        
        if hasattr(self, "pygletEventLoop"):
            self.pygletEventLoop.exit()

    def run(self, call_interval=1/10., installSignalHandlers=True):
        """Start the Pyglet event loop and Twisted reactor."""

        # Create a queue to hold Twisted events that will be executed
        # before stopping Twisted in the event that Pyglet has been stopped.
        self._postQueue = Queue.Queue()
        self._twistedQueue = Queue.Queue()

        if not hasattr(self, "pygletEventLoop"):
            log.msg("No Pyglet event loop registered. Using the default.")
            self.registerPygletEventLoop(EventLoop(self._twistedQueue, call_interval))
        else:
            self.pygletEventLoop.register_twisted_queue(self._twistedQueue, call_interval)
        
        # Start the Twisted thread.
        self.interleave(self._runInMainThread,
                        installSignalHandlers=installSignalHandlers)

        # Add events to handle Pyglet/Twisted shutdown events
        self.addSystemEventTrigger("after", "shutdown", self._stopPyglet)
        self.addSystemEventTrigger("after", "shutdown",
                                   lambda: self._postQueue.put(None))
        
        self.pygletEventLoop.run()

        # Now that the event loop has finished, remove
        # it so that further Twisted events are added to
        # the shutdown queue, and are dealt with below.
        del self.pygletEventLoop
        
        if not self._stopping:
            # The Pyglet event loop is no longer running, so we monitor the
            # queue containing Twisted events until all events are dealt with.
            self.stop()
            while 1:
                try:
                    f = self._postQueue.get(timeout=0.01)
                except Queue.Empty:
                    continue
                else:
                    # 'None' on the queue signifies the last Twisted event.
                    if f is None:
                        break
                    try:
                        f()
                    except:
                        log.err()
        
def install():
    """
    Setup Twisted+Pyglet integration based on the Pyglet event loop.
    """
    reactor = PygletReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
    return reactor


__all__ = ['install']
