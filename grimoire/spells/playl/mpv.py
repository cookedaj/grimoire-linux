# SPDX-License-Identifier: GPL-3.0-or-later
"""libmpv through ctypes (no Qt here): the client API (options, commands, properties, events) and the render API.

Why libmpv and not QtMultimedia: mpv plays practically everything, decodes on the GPU (nvdec/vaapi), renders .ass
subtitles with libass, keeps the pitch at other speeds and has track switching built in. libmpv2 ships with Kubuntu
(Haruna uses it); python-mpv isn't packaged, so this is a small ctypes binding of the parts PlayL uses.
mpv needs LC_NUMERIC "C" (it parses "1.5" with strtod); MPV() sets it, after Qt set the locale from the environment.
"""
import ctypes
import ctypes.util
import locale

LIB_NAMES = ("libmpv.so.2", "libmpv.so.1", "libmpv.so")
APT = "sudo apt install libmpv2"

# mpv_format
NONE, STRING, OSD_STRING, FLAG, INT64, DOUBLE, NODE, NODE_ARRAY, NODE_MAP, BYTE_ARRAY = range(10)
# mpv_event_id
EV_NONE, EV_SHUTDOWN, EV_LOG, EV_GET_REPLY, EV_SET_REPLY, EV_COMMAND_REPLY = 0, 1, 2, 3, 4, 5
EV_START_FILE, EV_END_FILE, EV_FILE_LOADED = 6, 7, 8
EV_VIDEO_RECONFIG, EV_AUDIO_RECONFIG, EV_SEEK, EV_PLAYBACK_RESTART, EV_PROPERTY_CHANGE = 17, 18, 20, 21, 22
# mpv_end_file_reason
END_EOF, END_STOP, END_QUIT, END_ERROR, END_REDIRECT = 0, 2, 3, 4, 5
# mpv_render_param_type
R_API_TYPE, R_GL_INIT, R_GL_FBO, R_FLIP_Y, R_BLOCK = 1, 2, 3, 4, 12
R_SW_SIZE, R_SW_FORMAT, R_SW_STRIDE, R_SW_POINTER = 17, 18, 19, 20
RENDER_FRAME = 1                       # mpv_render_context_update() flag: a new frame is due


class MpvError(Exception):
    pass


class _Node(ctypes.Structure):
    pass


class _NodeList(ctypes.Structure):
    _fields_ = [("num", ctypes.c_int), ("values", ctypes.POINTER(_Node)), ("keys", ctypes.POINTER(ctypes.c_char_p))]


class _ByteArray(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]


class _NodeU(ctypes.Union):
    _fields_ = [("string", ctypes.c_char_p), ("flag", ctypes.c_int), ("int64", ctypes.c_int64),
                ("double_", ctypes.c_double), ("list", ctypes.POINTER(_NodeList)),
                ("ba", ctypes.POINTER(_ByteArray))]


_Node._fields_ = [("u", _NodeU), ("format", ctypes.c_int)]


class _Event(ctypes.Structure):
    _fields_ = [("event_id", ctypes.c_int), ("error", ctypes.c_int), ("reply_userdata", ctypes.c_uint64),
                ("data", ctypes.c_void_p)]


class _EventProperty(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("format", ctypes.c_int), ("data", ctypes.c_void_p)]


class _EventEndFile(ctypes.Structure):
    _fields_ = [("reason", ctypes.c_int), ("error", ctypes.c_int)]


class _EventLog(ctypes.Structure):
    _fields_ = [("prefix", ctypes.c_char_p), ("level", ctypes.c_char_p), ("text", ctypes.c_char_p)]


class RenderParam(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("data", ctypes.c_void_p)]


GET_PROC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)


class GLInit(ctypes.Structure):
    # API 2.x has only these two fields; the spare pointer keeps an older libmpv from reading past the end
    _fields_ = [("get_proc_address", GET_PROC), ("ctx", ctypes.c_void_p), ("_spare", ctypes.c_void_p)]


class GLFbo(ctypes.Structure):
    _fields_ = [("fbo", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int), ("internal_format", ctypes.c_int)]


CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
_lib = None


def lib():
    """The loaded libmpv, or None when it isn't installed."""
    global _lib
    if _lib is None:
        names = list(LIB_NAMES) + [ctypes.util.find_library("mpv") or ""]
        for name in filter(None, names):
            try:
                _lib = ctypes.CDLL(name)
                break
            except OSError:
                continue
        else:
            _lib = False
            return None
        _declare(_lib)
    return _lib or None


def available() -> bool:
    return lib() is not None


def _declare(L):
    vp, cp, i = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int
    sig = {"mpv_create": (vp, []), "mpv_initialize": (i, [vp]), "mpv_terminate_destroy": (None, [vp]),
           "mpv_set_option_string": (i, [vp, cp, cp]), "mpv_command": (i, [vp, ctypes.POINTER(cp)]),
           "mpv_command_async": (i, [vp, ctypes.c_uint64, ctypes.POINTER(cp)]),
           "mpv_set_property": (i, [vp, cp, i, vp]), "mpv_set_property_string": (i, [vp, cp, cp]),
           "mpv_set_property_async": (i, [vp, ctypes.c_uint64, cp, i, vp]),
           "mpv_get_property": (i, [vp, cp, i, vp]), "mpv_observe_property": (i, [vp, ctypes.c_uint64, cp, i]),
           "mpv_request_log_messages": (i, [vp, cp]), "mpv_wait_event": (ctypes.POINTER(_Event), [vp, ctypes.c_double]),
           "mpv_set_wakeup_callback": (None, [vp, CALLBACK, vp]), "mpv_error_string": (cp, [i]),
           "mpv_free": (None, [vp]), "mpv_free_node_contents": (None, [ctypes.POINTER(_Node)]),
           "mpv_render_context_create": (i, [ctypes.POINTER(vp), vp, ctypes.POINTER(RenderParam)]),
           "mpv_render_context_render": (i, [vp, ctypes.POINTER(RenderParam)]),
           "mpv_render_context_set_update_callback": (None, [vp, CALLBACK, vp]),
           "mpv_render_context_update": (ctypes.c_uint64, [vp]),
           "mpv_render_context_report_swap": (None, [vp]),
           "mpv_render_context_free": (None, [vp])}
    for name, (res, args) in sig.items():
        f = getattr(L, name)
        f.restype, f.argtypes = res, args


def _node_value(n: _Node):
    f = n.format
    if f == STRING:
        return (n.u.string or b"").decode("utf-8", "replace")
    if f == FLAG:
        return bool(n.u.flag)
    if f == INT64:
        return n.u.int64
    if f == DOUBLE:
        return n.u.double_
    if f == NODE_ARRAY:
        lst = n.u.list.contents
        return [_node_value(lst.values[k]) for k in range(lst.num)]
    if f == NODE_MAP:
        lst = n.u.list.contents
        return {lst.keys[k].decode("utf-8", "replace"): _node_value(lst.values[k]) for k in range(lst.num)}
    return None


def _args(args) -> ctypes.Array:
    arr = (ctypes.c_char_p * (len(args) + 1))()
    arr[:-1] = [str(a).encode("utf-8", "surrogateescape") for a in args]   # file names that aren't UTF-8 too
    arr[-1] = None
    return arr


class MPV:
    """One mpv core. Methods return quickly (mpv runs its playback in its own threads); events are read with
    events() after the wakeup callback fires (it fires on mpv's thread: only signal the UI from it)."""

    def __init__(self, **options):
        L = lib()
        if L is None:
            raise MpvError("libmpv isn't installed")
        locale.setlocale(locale.LC_NUMERIC, "C")
        self.L = L
        self.h = L.mpv_create()
        if not self.h:
            raise MpvError("mpv_create failed")
        for k, v in options.items():
            self.set_option(k.replace("_", "-"), v)
        self._check(L.mpv_initialize(self.h), "initialize")
        self._wakeup = None
        self._observed: dict[int, str] = {}

    def _check(self, rc: int, what: str):
        """Raise MpvError for a negative return code (calls after close() come here as rc -1)."""
        if rc < 0:
            raise MpvError(f"{what}: {self.L.mpv_error_string(rc).decode()}")
        return rc

    @staticmethod
    def _text(v) -> bytes:
        if isinstance(v, bool):
            return b"yes" if v else b"no"
        return str(v).encode()

    def set_option(self, name: str, value):
        self._check(self.L.mpv_set_option_string(self.h, name.encode(), self._text(value)), f"option {name}")

    def command(self, *args):
        """Run a command (loadfile, seek, sub-add…); raises MpvError when mpv refuses it."""
        if not self.h:
            raise MpvError("mpv was closed")
        self._check(self.L.mpv_command(self.h, _args(args)), args[0])

    def command_async(self, *args, tag: int = 0):
        """Run a command without waiting for it (its result comes back as an EV_COMMAND_REPLY with tag)."""
        if not self.h:
            raise MpvError("mpv was closed")
        self._check(self.L.mpv_command_async(self.h, tag, _args(args)), args[0])

    def set(self, name: str, value):
        """Set a property: bool → flag, int → int64, float → double, else a string."""
        if not self.h:
            raise MpvError("mpv was closed")
        if isinstance(value, bool):
            data, fmt = ctypes.c_int(int(value)), FLAG
        elif isinstance(value, int):
            data, fmt = ctypes.c_int64(value), INT64
        elif isinstance(value, float):
            data, fmt = ctypes.c_double(value), DOUBLE
        else:
            self._check(self.L.mpv_set_property_string(self.h, name.encode(), str(value).encode()), name)
            return
        self._check(self.L.mpv_set_property(self.h, name.encode(), fmt, ctypes.byref(data)), name)

    def set_async(self, name: str, value: float):
        """Set a number property without waiting (seeking-like things the UI shouldn't block on)."""
        if not self.h:
            return
        data = ctypes.c_double(float(value))
        self.L.mpv_set_property_async(self.h, 0, name.encode(), DOUBLE, ctypes.byref(data))

    def get(self, name: str, default=None):
        """A property as a Python value (str/bool/int/float/list/dict), or default when it isn't available."""
        if not self.h:
            return default
        node = _Node()
        if self.L.mpv_get_property(self.h, name.encode(), NODE, ctypes.byref(node)) < 0:
            return default
        try:
            return _node_value(node)
        finally:
            self.L.mpv_free_node_contents(ctypes.byref(node))

    def observe(self, name: str):
        """Report changes of a property as ("property", name, value) events."""
        tag = len(self._observed) + 1
        self._observed[tag] = name
        self._check(self.L.mpv_observe_property(self.h, tag, name.encode(), NODE), f"observe {name}")

    def request_log(self, level: str = "error"):
        self.L.mpv_request_log_messages(self.h, level.encode())

    def on_wakeup(self, fn):
        """fn() is called from mpv's own thread whenever events are waiting; keep it tiny (emit a signal)."""
        self._wakeup = CALLBACK(lambda _d: fn())
        self.L.mpv_set_wakeup_callback(self.h, self._wakeup, None)

    def events(self):
        """Every waiting event, without blocking: ("property", name, value), ("end-file", reason, error),
        ("log", level, text), ("file-loaded",), ("shutdown",), ("seek",), ("restart",), ("command", tag, error)."""
        while self.h:
            ev = self.L.mpv_wait_event(self.h, 0).contents
            eid = ev.event_id
            if eid == EV_NONE:
                return
            if eid == EV_PROPERTY_CHANGE:
                prop = ctypes.cast(ev.data, ctypes.POINTER(_EventProperty)).contents
                value = None
                if prop.format == NODE and prop.data:
                    value = _node_value(ctypes.cast(prop.data, ctypes.POINTER(_Node)).contents)
                yield ("property", prop.name.decode(), value)
            elif eid == EV_END_FILE:
                end = ctypes.cast(ev.data, ctypes.POINTER(_EventEndFile)).contents
                yield ("end-file", end.reason, end.error)
            elif eid == EV_LOG:
                log = ctypes.cast(ev.data, ctypes.POINTER(_EventLog)).contents
                yield ("log", (log.level or b"").decode(), (log.text or b"").decode("utf-8", "replace").strip())
            elif eid == EV_FILE_LOADED:
                yield ("file-loaded",)
            elif eid == EV_START_FILE:
                yield ("start-file",)
            elif eid == EV_SHUTDOWN:
                yield ("shutdown",)
                return
            elif eid == EV_SEEK:
                yield ("seek",)
            elif eid == EV_PLAYBACK_RESTART:
                yield ("restart",)
            elif eid == EV_COMMAND_REPLY:
                yield ("command", ev.reply_userdata, ev.error)

    def error_text(self, code: int) -> str:
        return self.L.mpv_error_string(code).decode()

    def close(self):
        """Stop and free the core (free a render context made on it first)."""
        if self.h:
            h, self.h = self.h, None
            self.L.mpv_terminate_destroy(h)


def params(*pairs) -> ctypes.Array:
    """A render-param array from (type, value) pairs, INVALID-terminated. A c_char_p or c_void_p is passed as the
    pointer itself (API type, SW format, SW buffer), an array as its first element, anything else by reference.
    The caller keeps the values alive until mpv is done with the array."""
    arr = (RenderParam * (len(pairs) + 1))()
    for k, (t, obj) in enumerate(pairs):
        arr[k].type = t
        if obj is None:
            arr[k].data = None
        elif isinstance(obj, (ctypes.c_char_p, ctypes.c_void_p, ctypes.Array)):
            arr[k].data = ctypes.cast(obj, ctypes.c_void_p)
        else:
            arr[k].data = ctypes.cast(ctypes.pointer(obj), ctypes.c_void_p)
    return arr
