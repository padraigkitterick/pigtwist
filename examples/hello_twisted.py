"""A simple example of Pyglet/Twisted integration. A Pyglet window
is displayed, and both Pyglet and Twisted are making scheduled calls
and regular intervals. Interacting with the window doesn't interfere
with either calls.
"""
import pyglet

import pygletreactor
pygletreactor.install() # <- this must come before...
from twisted.internet import reactor, task # <- ...importing this reactor!

# Create a Pyglet window with a simple message
window = pyglet.window.Window()
label = pyglet.text.Label('hello world',
                          x = window.width / 2,
                          y = window.height / 2,
                          anchor_x = 'center',
                          anchor_y = 'center')

@window.event
def on_draw():
    window.clear()
    label.draw()

@window.event
def on_close():
    reactor.callFromThread(reactor.stop)
    
    # Return true to ensure that no other handlers
    # on the stack receive the on_close event
    return True

# Schedule a function call in Pyglet
def runEverySecondPyglet(dt):
    print "pyglet call: one second has passed"
pyglet.clock.schedule_interval(runEverySecondPyglet, 1)

# Schedule a function call in Twisted
def runEverySecondTwisted():
    print "twisted call: 1.5 seconds have passed"
l = task.LoopingCall(runEverySecondTwisted)
l.start(1.5)

# Start the reactor
reactor.run()

