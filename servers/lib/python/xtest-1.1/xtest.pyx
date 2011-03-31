
""" use XTest to simulate key presses, including multi-key presses
such as Control-Shift-Alt-space

see http://hoopajoo.net/projects/xautomation.html (gnu) for other examples

see http://homepage3.nifty.com/tsato/xvkbd/events.html for more about
keys with modifiers """

cdef extern from "X11/Xlib.h":
    ctypedef struct Display
    
    Display *XOpenDisplay(char* display_name)
    int XCloseDisplay(Display *display)
    int XFlush(Display* display)

    ctypedef unsigned int XID
    ctypedef XID KeySym

    ctypedef unsigned char KeyCode

    KeySym XStringToKeysym(char* string)
    KeyCode XKeysymToKeycode(Display* display, KeySym keysym)
NoSymbol = 0 
CurrentTime = long(0) #   /* special Time */

cdef extern from "X11/extensions/XTest.h":
    int XTestFakeKeyEvent(Display* dpy, unsigned int keycode,
                          int is_press, # (actually Bool)
                          unsigned long delay)

    
    int XTestFakeButtonEvent(Display *display, unsigned int button,
                             int is_press, # (actually Bool)
                             unsigned long delay)

    int XTestFakeMotionEvent(Display *display, int screen_number,
                             int x, int y, unsigned long delay)

cdef keycode(Display *dpy, key_string):
    cdef KeyCode kc
    cdef KeySym ks

    ks = XStringToKeysym(key_string)
    if ks == NoSymbol:
        raise ValueError("no symbol for key %r" % key_string)

    kc = XKeysymToKeycode(dpy, ks)
    return <int>kc

cdef class XTest:
    cdef Display *dpy
    def __init__(self, display=":0.0"):
        self.dpy = XOpenDisplay(display)
        if self.dpy is NULL:
            raise ValueError("unable to open display %r" % display)

    def __dealloc__(self):
        XCloseDisplay(self.dpy)

    def fakeKeyEvent(self, key, down=True, up=True):
        """key is a Tk-style list of modifiers and key name, such as:

        'p'
        'P' # same as 'Shift-p'
        'Shift-p'
        'Alt-Shift-p'
        'space'

        This function can send both down and up events (for all the
        required keys), or you can disable the down or up steps by
        setting those args to False.
        
        """
        cdef Display *d
        d = self.dpy

        if key == '-':
            key = 'minus'
        if key.isupper():
            key = "Shift-%s" % key

        presses = []
        for k in key.split('-'):
            if k in ['Shift','Alt','Control']:
                k = '%s_L' % k
            presses.append(keycode(self.dpy, k))

        if down:
            for k in presses:
                XTestFakeKeyEvent(d, k, True, CurrentTime)
        if up:
            for k in presses[::-1]:
                XTestFakeKeyEvent(d, k, False, CurrentTime)
        XFlush(d)
      
    def fakeButtonEvent(self, button, is_press):
        """
        button is the "logical button" according to the XTestFakeButtonEvent
        man page. It seems like 0 is the LMB, etc.
        
        Set is_press to True for a press; False for a release
        """
        cdef Display *d
        d = self.dpy
        XTestFakeButtonEvent(d, button, is_press, CurrentTime)

    def fakeMotionEvent(self, x, y, screen_number=-1):
        """
        x, y are coordinates on a screen.

        The default is to use the screen that the pointer is currently
        on, but you can pass an alternate screen number.
        """
        cdef Display *d
        d = self.dpy
        XTestFakeMotionEvent(d, screen_number, x, y, CurrentTime)
