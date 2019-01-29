#!flask/bin/python
import requests
import os
import sys
import logging
import datetime
import time
import opentracing
import logging

from flask import Flask, request, session
from flask import _request_ctx_stack as stack
from flask_prometheus import monitor
from jaeger_client import Config, Tracer, ConstSampler
from jaeger_client.reporter import NullReporter
from jaeger_client.codecs import B3Codec
from opentracing.ext import tags
from opentracing.propagation import Format

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.DEBUG)

greeterUrl = os.environ.get('GREETERSERVICE') if os.environ.get('GREETERSERVICE') != None else 'http://localhost:8080'
app.logger.debug('GREETERSERVICE: ' + greeterUrl)

nameserviceUrl = os.environ.get('NAMESERVICE') if os.environ.get('NAMESERVICE') != None else 'http://localhost:8081'
app.logger.debug('NAMESERVICE: ' + nameserviceUrl)

#tracer = Tracer(
#    one_span_per_rpc=True,
#    service_name='productpage',
#    reporter=NullReporter(),
#    sampler=ConstSampler(decision=True),
#    extra_codecs={Format.HTTP_HEADERS: B3Codec()}
#)

def init_tracer(service):
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name=service,
    )
    return config.initialize_tracer()

tracer = init_tracer('hello-world')

@app.route('/')
def index():
    # Get Headers
    # headers = getForwardHeaders(request)
    with tracer.start_span('say-hello') as span:
        # Call Greeter Service
        span.set_tag('hello', 'begin')
        status, greeting = getGreeting(span)
        app.logger.debug('GREETER-RESPONSE: ' + greeting)

        # Call Name Service
        status, name = getName(span) 
        app.logger.debug('NAME-RESPONSE: ' + name)
        timestamp = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return "%s %s, %s!\n" % (timestamp, greeting, name)

def getGreeting(root_span):
    with tracer.start_span('greeting', child_of=root_span) as span:
        try: 
            app.logger.debug('GETTING GREETING')
            res = http_get(greeterUrl, root_span)
            app.logger.debug('GOT GREETING')
            span.log_kv({'event': 'get-greeting', 'value': res.text})
        except:
            res = None
        if res and res.status_code == 200:
            return 200, res.text
        else:
            status = res.status_code if res is not None and res.status_code else 500
            return status, 'Sorry, greetings not available.'

def getName(root_span):
    with tracer.start_active_span('get-name', child_of=root_span) as span:
        try: 
            res = http_get(nameserviceUrl, root_span)
            span.log_kv({'event': 'get-name', 'value': res.text})
        except:
            res = None
        if res and res.status_code == 200:
            return 200, res.text
        else:
            status = res.status_code if res is not None and res.status_code else 500
            return status, 'Sorry, name service not available.'

def http_get(url, root_span):
    # span = tracer.active_span
    app.logger.debug('ENTERED HTTP GET')
    root_span.set_tag(tags.HTTP_METHOD, 'GET')
    root_span.set_tag(tags.HTTP_URL, url)
    root_span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
    headers = {}
    tracer.inject(span, Format.HTTP_HEADERS, headers)

    r = requests.get(url, headers=headers)
    app.logger.debug('REQUEST STATUS CODE: ' + r.status_code)
    assert r.status_code == 200
    return r

if __name__ == '__main__':
    monitor(app, port=8000)
    app.run(host='0.0.0.0', port=8080)
