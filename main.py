#!/usr/bin/env python
import json
import logging
import webapp2

import keccak
from google.appengine.ext import ndb

hashFunctions = {
    'keccak256': lambda data: keccak.Keccak256(data).hexdigest(),
}

class Preimage(ndb.Model):
    text = ndb.StringProperty(indexed=False)
    function = ndb.StringProperty(choices=hashFunctions.keys(), indexed=False)

    @classmethod
    def create(cls, function, text):
        return cls(id=hashFunctions[function](text), text=text, function=function)


def jsonapi(fun):
    def wrap(self, *args, **kwargs):
        if self.request.content_type.lower() != "application/json":
            self.response.status = '400 Bad Request'
            response = {"status": "error", "error": "Content-type must be application/json"}
        else:
            try:
                data = json.loads(self.request.body)
            except Exception, e:
                logging.exception("Decoding JSON body")
                self.response.status = '400 Bad Request'
                response = {"status": "error", "error": "Could not decode request body"}
            else:
                response = fun(self, data, *args, **kwargs)

        if self.request.GET.get('callback') != None:
            response = "%s(%s);" % (self.request.GET['callback'], response)
        self.response.write(json.dumps(response))
    return wrap


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('Hello world!')


class SubmitHandler(webapp2.RequestHandler):
    @jsonapi
    def post(self, data, funcname):
        if funcname not in hashFunctions:
            self.response.status = '400 Bad Request'
            return {"status": "error", "error": "Invalid hash function %s" % (funcname,)}
            return

        preimages = [Preimage.create(funcname, value) for value in data]
        ndb.put_multi(preimages)
        return {"status": "ok"}


class BulkQueryHandler(webapp2.RequestHandler):
    @jsonapi
    def post(self, data, funcname):
        keys = [ndb.Key(Preimage, hashvalue) for hashvalue in data]
        preimages = ndb.get_multi(keys)
        return {"status": "ok", "data": [preimage.text if preimage else None for preimage in preimages]}


class QueryOneHandler(webapp2.RequestHandler):
    def get(self, funcname, hashvalue):
        obj = Preimage.get_by_id(hashvalue.lower())
        if obj is None:
            self.response.status = '404 Not Found'
            return
        self.response.content_type = "text/plain"
        self.response.write(obj.text)


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/([\d\w]+)/submit', SubmitHandler),
    ('/([\d\w]+)/query', BulkQueryHandler),
    ('/([\d\w]+)/([0-9a-fA-F]+)', QueryOneHandler),
], debug=True)
