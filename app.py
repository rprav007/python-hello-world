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
from opentracing_instrumentation.request_context import get_current_span, span_in_context

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

#tracer = init_tracer('hello-world')
tracer = Tracer(
    one_span_per_rpc=True,
    service_name='hello-world-service',
    reporter=NullReporter(),
    sampler=ConstSampler(decision=True),
    extra_codecs={Format.HTTP_HEADERS: B3Codec()}
)

def trace():
    '''
    Function decorator that creates opentracing span from incoming b3 headers
    '''
    def decorator(f):
        def wrapper(*args, **kwargs):
            request = stack.top.request
            try:
                # Create a new span context, reading in values (traceid,
                # spanid, etc) from the incoming x-b3-*** headers.
                span_ctx = tracer.extract(
                    Format.HTTP_HEADERS,
                    dict(request.headers)
                )
                # Note: this tag means that the span will *not* be
                # a child span. It will use the incoming traceid and
                # spanid. We do this to propagate the headers verbatim.
                rpc_tag = {tags.SPAN_KIND: tags.SPAN_KIND_RPC_SERVER}
                span = tracer.start_span(
                    operation_name='op', child_of=span_ctx, tags=rpc_tag
                )
            except Exception as e:
                # We failed to create a context, possibly due to no
                # incoming x-b3-*** headers. Start a fresh span.
                # Note: This is a fallback only, and will create fresh headers,
                # not propagate headers.
                span = tracer.start_span('op')
            with span_in_context(span):
                r = f(*args, **kwargs)
                return r
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def getForwardHeaders(request):
    headers = {}

    # x-b3-*** headers can be populated using the opentracing span
    span = get_current_span()
    carrier = {}
    tracer.inject(
        span_context=span.context,
        format=Format.HTTP_HEADERS,
        carrier=carrier)

    headers.update(carrier)

    # We handle other (non x-b3-***) headers manually
    if 'user' in session:
        headers['end-user'] = session['user']

    incoming_headers = ['x-request-id']

    # Add user-agent to headers manually
    if 'user-agent' in request.headers:
        headers['user-agent'] = request.headers.get('user-agent')

    for ihdr in incoming_headers:
        val = request.headers.get(ihdr)
        if val is not None:
            headers[ihdr] = val
            #print "incoming: "+ihdr+":"+val

    return headers

@app.route('/')
@trace()
def index():
#    request = stack.top.request
#    span_ctx = tracer.extract(Format.HTTP_HEADERS, dict(request.headers))
#    span_tags = {tags.SPAN_KIND: tags.SPAN_KIND_RPC_SERVER}
    status, greeting = getGreeting()
    status, name = getName() 
    timestamp = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    return "%s %s, %s!\n" % (timestamp, greeting, name)

#   with tracer.start_span('say-hello', child_of=span_ctx, tags=span_tags) as span:
#       # Call Greeter Service
#       span.set_tag('hello', 'begin')
#       status, greeting = getGreeting(span)
#       app.logger.debug('GREETER-RESPONSE: ' + greeting)
#
#       # Call Name Service
#       status, name = getName(span) 
#       app.logger.debug('NAME-RESPONSE: ' + name)
#       timestamp = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
#       return "%s %s, %s!\n" % (timestamp, greeting, name)

def getGreeting():
    try: 
        headers = getForwardHeaders(request)
        app.logger.debug('GETTING GREETING')
        res = http_get(greeterUrl, headers)
        app.logger.debug('GOT GREETING')
    except:
        res = None
    if res and res.status_code == 200:
        return 200, res.text
    else:
        status = res.status_code if res is not None and res.status_code else 500
        return status, 'Sorry, greetings not available.'

def getName():
    try: 
        headers = getForwardHeaders(request)
        res = http_get(nameserviceUrl, headers)
    except:
        res = None
    if res and res.status_code == 200:
        return 200, res.text
    else:
        status = res.status_code if res is not None and res.status_code else 500
        return status, 'Sorry, name service not available.'

    
#def getGreeting(root_span):
#    with tracer.start_span('greeting', child_of=root_span) as span:
# #       app.logger.debug('GETTING GREETING')
# #       res = http_get(greeterUrl, root_span)
# #       span.log_kv({'event': 'get-greeting', 'value': res.text})
# #       return 200, res.text      
#        try: 
#            app.logger.debug('GETTING GREETING')
#            res = http_get(greeterUrl, root_span)
#            app.logger.debug('GOT GREETING')
#            span.log_kv({'event': 'get-greeting', 'value': res.text})
#        except:
#            res = None
#        if res and res.status_code == 200:
#            return 200, res.text
#        else:
#            status = res.status_code if res is not None and res.status_code else 500
#            return status, 'Sorry, greetings not available.'
#
#def getName(root_span):
#    with tracer.start_span('get-name', child_of=root_span) as span:
#        try: 
#            res = http_get(nameserviceUrl, root_span)
#            span.log_kv({'event': 'get-name', 'value': res.text})
#        except:
#            res = None
#        if res and res.status_code == 200:
#            return 200, res.text
#        else:
#            status = res.status_code if res is not None and res.status_code else 500
#            return status, 'Sorry, name service not available.'

def http_get(url, headers):
    r = requests.get(url, headers=headers)
    assert r.status_code == 200
    return r 

#def http_get(url, root_span):
#    # span = tracer.active_span
#    app.logger.debug('ENTERED HTTP GET')
#    root_span.set_tag(tags.HTTP_METHOD, 'GET')
#    root_span.set_tag(tags.HTTP_URL, url)
#    root_span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
#    headers = {}
#    tracer.inject(root_span, Format.HTTP_HEADERS, headers)
#    
#    app.logger.debug('GETTING: ' + url)
#
#    r = requests.get(url, headers=headers)
#    # app.logger.debug('REQUEST STATUS CODE: ' + r.status_code)
#    assert r.status_code == 200
#    return r

if __name__ == '__main__':
    monitor(app, port=8000)
    app.run(host='0.0.0.0', port=8080)
