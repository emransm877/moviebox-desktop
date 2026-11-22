"""Wire-level gzip API responses preserve Unicode, headers and bounded failures."""
import gzip
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
from json_transport import read_json
from native_mobile import NativeMovieBox
from service import MovieBoxService


class Response(io.BytesIO):
    def __init__(self, body, encoding=''):
        super().__init__(body);self.headers={'Content-Encoding':encoding}


class JsonTransportTests(unittest.TestCase):
    def test_gzip_identity_and_stale_charset_preserve_opaque_values(self):
        data={'title':'\u09ac\u09be\u0982\u09b2\u09be \u00e9 \u65e5\u672c\u8a9e','id':'opaque-\u00c3\u00a9','url':'https://example.test/\u00e2\u20ac\u2122','subtitle':'literal \u00c2\u00b7 cue'}
        raw=json.dumps(data,ensure_ascii=False).encode()
        for body,encoding in [(raw,''),(raw,'identity'),(gzip.compress(raw),'gzip')]:
            response=Response(body,encoding);response.headers['Content-Type']='application/json; charset=iso-8859-1'
            self.assertEqual(read_json(response),data)

    def test_malformed_truncated_and_trailing_gzip_fail(self):
        body=gzip.compress(b'{"title":"owned"}')
        for payload in [b'not gzip',body[:-4],body+b'trailing']:
            with self.assertRaises(ValueError):read_json(Response(payload,'gzip'))

    def test_encoded_and_decoded_size_limits(self):
        with self.assertRaisesRegex(ValueError,'encoded size'):read_json(Response(b' '*101),encoded_limit=100)
        with self.assertRaisesRegex(ValueError,'decoded size'):read_json(Response(gzip.compress(b' '*1000),'gzip'),decoded_limit=100)
        with self.assertRaisesRegex(ValueError,'decoded size'):read_json(Response(b' '*101),decoded_limit=100)

    def test_only_advertised_gzip_is_decoded_and_json_is_strict_utf8(self):
        for body,encoding in [(gzip.compress(b'{}'),''),(b'{"title":"\xff"}',''),(b'{}','br')]:
            with self.assertRaises((ValueError,UnicodeError)):read_json(Response(body,encoding))

    def test_actual_http_gzip_negotiation_and_user_headers_for_both_clients(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(dict(self.headers))
                body=gzip.compress(json.dumps({'code':0,'data':{'title':'\u09ac\u09be\u0982\u09b2\u09be','opaque':'\u00c3\u00a9-id'}},ensure_ascii=False).encode())
                self.send_response(200);self.send_header('Content-Encoding','gzip');self.send_header('Content-Type','application/json; charset=iso-8859-1')
                self.send_header('x-user',json.dumps({'token':'owned-guest-fixture'}));self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*_):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        api=MovieBoxService(use_native=False);native=NativeMovieBox(host='http://127.0.0.1:'+str(server.server_port))
        try:
            with patch('service.API','http://127.0.0.1:'+str(server.server_port)):
                self.assertEqual(api.request('/owned')['title'],'\u09ac\u09be\u0982\u09b2\u09be')
            self.assertEqual(native.request('/owned')['opaque'],'\u00c3\u00a9-id')
            self.assertEqual(api.token,'owned-guest-fixture');self.assertEqual(native.token,'owned-guest-fixture')
            self.assertTrue(all(request.get('Accept-Encoding')=='gzip' for request in requests))
            self.assertTrue(any(key.lower()=='x-tr-signature' for key in requests[-1]))
        finally:
            api.close();server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
