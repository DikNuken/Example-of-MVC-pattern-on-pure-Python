# ===========================
# Example of MVC pattern on pure Python. Whiten for "Use Python in the Web"
# course. Institute Mathematics and Computer Science at Ural Federal University
# in 2014.
#
# By Pahaz Blinov.
# ===========================
import uuid

__author__ = "pahaz"

DB_FILE = "main.db"
DB_SESSIONS_FILE = "sessions.db"
DEBUG = False

# ===========================
#
#        Utilities
#
# ===========================

from urlparse import parse_qs
import shelve


def http_status(code):
    """
    Return a str representation of HTTP response status from int `code`.
    """
    return "200 OK" if code == 200 else "404 Not Found"


def parse_http_post_data(environ):
    """
    Parse a HTTP post data form WSGI `environ` argument.
    """
    try:
        request_body_size = int(environ.get("CONTENT_LENGTH", 0))
    except ValueError:
        request_body_size = 0

    request_body = environ["wsgi.input"].read(request_body_size)
    body_query_dict = parse_qs(request_body)

    return body_query_dict


def parse_http_get_data(environ):
    return parse_qs(environ["QUERY_STRING"])


def parse_cookies(environ):
    return dict([map(lambda s: s.strip(), x.split('=')) for x in environ['HTTP_COOKIE'].split(';')])


def take_one_or_None(dict_, key):
    """
    Take one value by key from dict or return None.

        >>> d = {"foo":[1,2,3], "baz":7}
        >>> take_one_or_None(d, "foo")
        1
        >>> take_one_or_None(d, "bar") is None
        True
        >>> take_one_or_None(d, "baz")
        7
    """
    val = dict_.get(key)
    if type(val) in (list, tuple) and len(val) > 0:
        val = val[0]
    return val


# ===========================
#
#         1. Model
#
# ===========================


class TextModel(object):
    def __init__(self, title, content):
        self.title = title
        self.content = content


class TextManager(object):
    def __init__(self):
        self._db = shelve.open(DB_FILE)

    def get_by_title(self, title):
        """
        Get Text object by name if exist else return None.
        """
        content = self._db.get(title)
        return TextModel(title, content) if content else None

    def get_all(self):
        """
        Get list of all Text objects.
        """
        return [
            TextModel(title, content) for title, content in self._db.items()
        ]

    def create(self, title, content):
        if title in self._db:
            return False

        self._db[title] = content
        self._db.sync()
        return True

    def delete(self, title):
        if title not in self._db:
            return False

        del self._db[title]
        self._db.sync()
        return True


class SessionModel():
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.amount_of_viewed_pages = 0


class SessionManager():
    def __init__(self):
        self._db = shelve.open(DB_SESSIONS_FILE)


    def get_or_create(self, session_id):
        session = self._db.get(session_id)
        if not session:
            session = SessionModel()
            self._db[session.session_id] = session
            self._db.sync()
        return session

    def update(self, session):
        self._db[session.session_id] = session
        self._db.sync()


# ===========================
#
#   Controller and Router
#
# ===========================

class Router(object):
    """
    Router for requests.

    """

    def __init__(self):
        self._paths = {}

    def route(self, request_path, request_get_data):

        if request_path in self._paths:
            res = self._paths[request_path](request_get_data)
        else:
            res = self.default_response(request_get_data)

        return res

    def register(self, path, callback):
        self._paths[path] = callback

    def default_response(self, *args):
        return 404, "Nooo 404!"


class TextController(object):
    def __init__(self, index_view, add_view, manager):
        self.index_view = index_view
        self.add_view = add_view
        self.model_manager = manager

    def index(self, request_get_data):
        title = take_one_or_None(request_get_data, "title")
        current_text = self.model_manager.get_by_title(title) \
            if request_get_data["SESSION"].amount_of_viewed_pages <= 3 else None

        all_texts = self.model_manager.get_all()

        context = {
            "all": all_texts,
            "current": current_text,
            "error": "Too many articles reviewed." if request_get_data["SESSION"].amount_of_viewed_pages > 3 else ""
        }
        if current_text:
            request_get_data["SESSION"].amount_of_viewed_pages += 1

        return 200, self.index_view.render(context)

    def add(self, request_get_data):
        title = take_one_or_None(request_get_data, 'title')
        content = take_one_or_None(request_get_data, 'content')

        if not title or not content:
            error = "Need fill the form fields."
        else:
            error = None
            is_created = self.model_manager.create(title, content)
            if not is_created:
                error = "Title already exist."

        context = {
            'title': title,
            'content': content,
            'error': error,
        }
        return 200, self.add_view.render(context)


# ===========================
#
#           View
#
# ===========================

class TextIndexView(object):
    @staticmethod
    def render(context):
        context["titles"] = "\n".join([
            "<li>{text.title}</li>".format(text=text) for text in context["all"]
        ])

        if context["current"]:
            context["content"] = """
            <h1>{current.title}</h1>
            {current.content}
            """.format(current=context["current"])
        else:
            context["content"] = 'What do you want read?'
        if context["error"]:
            context["error"] = """
            <h1 style="color:red;">{error}</h1>
            """.format(error=context["error"])

        t = """
        <form method="GET">
            <input type=text name=title placeholder="Text title" />
            <input type=submit value=read />
        </form>
        <form method="GET" action="/text/add">
            <input type=text name=title placeholder="Text title" /> <br>
            <textarea name=content placeholder="Text content!" ></textarea> <br>
            <input type=submit value=write/rewrite />
        </form>
        <div>{error}</div>
        <div>{content}</div>
        <ul>{titles}</ul>
        """
        return t.format(**context)


class RedirectView(object):
    @staticmethod
    def render(context):
        return '<meta http-equiv="refresh" content="0; url=/text" />'


# ===========================
#
#          Main
#
# ===========================

text_manager = TextManager()
controller = TextController(TextIndexView, RedirectView, text_manager)

router = Router()
router.register("/", lambda x: (200, "Index HI!"))
router.register("/text", controller.index)
router.register("/text/add", controller.add)


# ===========================
#
#          WSGI
#
# ===========================

def application(environ, start_response):
    request_path = environ["PATH_INFO"]
    request_get_data = parse_http_get_data(environ)
    cookies = parse_cookies(environ)
    session = SessionManager().get_or_create(take_one_or_None(cookies, "session_id"))
    request_get_data['SESSION'] = session
    # TODO: You can add this interesting line
    # print(parse_http_post_data(environ))

    http_status_code, response_body = router.route(request_path, request_get_data)
    SessionManager().update(session)
    if DEBUG:
        response_body += "<br><br> The request ENV: {0}".format(repr(environ))

    response_status = http_status(http_status_code)
    response_headers = [("Content-Type", "text/html"),
                        ("Set-Cookie", "session_id=" + session.session_id), ]

    start_response(response_status, response_headers)
    return [response_body]  # it could be any iterable.


# if run as script do tests.
if __name__ == "__main__":
    import doctest

    doctest.testmod()