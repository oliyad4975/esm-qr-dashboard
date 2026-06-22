import urllib.request
from urllib.error import HTTPError
for path in ['http://127.0.0.1:5000/','http://127.0.0.1:5000/login','http://127.0.0.1:5000/register']:
    try:
        resp = urllib.request.urlopen(path)
        print(path, resp.status)
        print(resp.read(200))
    except HTTPError as e:
        print(path, 'HTTPError', e.code)
        print(e.read(200))
    except Exception as e:
        print(path, type(e).__name__, e)
