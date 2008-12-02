"""
This module provides Pyglet/Twisted integration using
the new (Pyglet v1.1) pyglet.app event loop.

To use this reactor, include the following statements
_before_ importing the standard Twisted reactor:

    import pygletreactor
    pygletreactor.install()

Then, register the standard Pyglet event loop with Twisted:

    from twisted.internet import reactor
    reactor.registerPygletEventLoop(pyglet.app.EventLoop)
    reactor.run()

Or, if you have subclassed pyglet.app.EventLoop:

    from twisted.internet import reactor
    reactor.registerPygletEventLoop(yourEventLoop)
    reactor.run()

Although it's usual to stop the reactor using reactor.stop(),
this still causes problems with the current implementation.
Therefore, call EventLoop.exit() or close all Pyglet windows,
which (usually) results in a clean Pyglet+Twisted shutdown.

Based on the wxPython reactor (wxreactor.py) that ships with Twisted.

Padraig Kitterick <p.kitterick@psych.york.ac.uk>
"""

import Queue

import pyglet

from twisted.python import log, runtime
from twisted.internet import _threadedselect

clock = pyglet.clock.get_default()

class PygletReactor(_threadedselect.ThreadedSelectReactor):
    """
    Pyglet reactor.

    Twisted events are integrated into the Pyglet event loop.
    """

    _stopping = False

    def registerPygletEventLoop(self, eventloop):
        """Register the pyglet.app.EventLoop instance."""
        self.pygletEventLoop = eventloop
    
    def stop(self):
        """Stop Twisted."""
        if self._stopping:
            return
        self._stopping = True
        _threadedselect.ThreadedSelectReactor.stop(self)

    def _runInMainThread(self, f):
        """Schedule Twisted function calls in the Pyglet event loop."""
        if hasattr(self, "pygletEventLoop"):
            # Schedule the function call a short time (10 ms) in the future.
            # It should be possible to reduce the time to < 10 ms but
            # that occasionally causes Twisted to get stuck...
            clock.schedule_once(lambda dt, func: func(), 0.01, f)
        else:
            # If Pyglet has stopped, add the events to a queue which
            # is processed prior to shutting Twisted down.
            self._postQueue.put(f)

    def _stopPyglet(self):
        """Stop the pyglet event loop."""
        if hasattr(self, "pygletEventLoop"):
            self.pygletEventLoop.exit()

    def run(self, installSignalHandlers=True):
        """Start the Pyglet event loop and Twisted reactor."""

        # Create a queue to hold Twisted events that will be executed
        # before stopping Twisted in the event that Pyglet has been stopped.
        self._postQueue = Queue.Queue()
        
        if not hasattr(self, "pygletEventLoop"):
            log.msg("No Pyglet event loop registered. Using the default.")
            self.registerPygletEventLoop(pyglet.app.EventLoop())

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
