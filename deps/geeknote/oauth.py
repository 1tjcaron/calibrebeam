# -*- coding: utf-8 -*-

import httplib
import time
import Cookie
import uuid
from urllib import urlencode, unquote
from urlparse import urlparse

import logging

#FORMAT = "%(filename)s %(funcName)s %(lineno)d : %(message)s"
#logging.basicConfig(format=FORMAT, level=logging.DEBUG)


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

class GeekNoteAuth(object):
                 #my dev keys
    consumerKey = "1tjcaron-3617" #config.CONSUMER_KEY
    consumerSecret = "5f3e4368a027d923" #config.CONSUMER_SECRET
    exitErr = False

    url = {
        "base": 'sandbox.evernote.com', #config.USER_BASE_URL,
        "oauth": "/OAuth.action?oauth_token=%s",
        "access": "/OAuth.action",
        "token" : "/oauth",
        "login" : "/Login.action",
        "tfa"   : "/OTCAuth.action",
    }

    cookies = {}

    postData = {
        'login': {
            'login': 'Sign in',
            'username': '',
            'password': '',
            'targetUrl': None,
        },
        'access': {
            'authorize': 'Authorize',
            'oauth_token': None,
            'oauth_callback': None,
            'embed': 'false',
        },
        'tfa': {
            'code': '',
            'login': 'Sign in',
        },
    }

    username = None
    password = None
    tmpOAuthToken = None
    verifierToken = None
    OAuthToken = None
    incorrectLogin = 0
    incorrectCode = 0
    code = None

    def getTokenRequestData(self, **kwargs):
        params = {
            'oauth_consumer_key': self.consumerKey,
            'oauth_signature': self.consumerSecret + '%26',
            'oauth_signature_method': 'PLAINTEXT',
            'oauth_timestamp': str(int(time.time())),
            'oauth_nonce': uuid.uuid4().hex
        }

        if kwargs:
            params = dict(params.items() + kwargs.items())

        return params

    def loadPage(self, url, uri=None, method="GET", params=""):
        if not url:
            logging.error("Request URL undefined")
            self.exitErr = True
            return

        if not uri:
            urlData = urlparse(url)
            url = urlData.netloc
            uri = urlData.path + '?' + urlData.query

        # prepare params, append to uri
        if params:
            params = urlencode(params)
            if method == "GET":
                uri += ('?' if uri.find('?') == -1 else '&') + params
                params = ""

        # insert local cookies in request
        headers = {
            "Cookie": '; '.join([key + '=' + self.cookies[key] for key in self.cookies.keys()])
        }

        if method == "POST":
            headers["Content-type"] = "application/x-www-form-urlencoded"

        logging.debug("Request URL: %s:/%s > %s # %s", url,
                      uri, unquote(params), headers["Cookie"])

        conn = httplib.HTTPSConnection(url)
        conn.request(method, uri, params, headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()

        logging.debug("Response : %s > %s",
                      response.status,
                      response.getheaders())
        result = Struct(status=response.status,
                              location=response.getheader('location', None),
                              data=data)

        # update local cookies
        sk = Cookie.SimpleCookie(response.getheader("Set-Cookie", ""))
        for key in sk:
            self.cookies[key] = sk[key].value
        # delete cookies whose content is "deleteme"
        for key in self.cookies.keys():
            if self.cookies[key] == "deleteme":
                del self.cookies[key]

        return result

    def parseResponse(self, data):
        data = unquote(data)
        return dict(item.split('=', 1) for item in data.split('?')[-1].split('&'))

    def getToken(self, username, password):
        #out.preloader.setMessage('Authorize...')
        self.getTmpOAuthToken()
        if self.exitErr:
            logging.error("getTmpOAuthToken")
            return "ERROR"

        self.login(username, password)
        if self.exitErr:
            logging.error("login")
            return "ERROR"

        #out.preloader.setMessage('Allow Access...')
        self.allowAccess()
        if self.exitErr:
            logging.error("allowAccess")
            return "ERROR"

        #out.preloader.setMessage('Getting Token...')
        self.getOAuthToken()
        if self.exitErr:
            logging.error("getOAuthToken")
            return "ERROR"

        #out.preloader.stop()
        return self.OAuthToken

    def getTmpOAuthToken(self):
        response = self.loadPage(self.url['base'],
                                 self.url['token'],
                                 "GET",
                                 self.getTokenRequestData(
                                     oauth_callback="https://" + self.url['base']
                                 ))

        if response.status != 200:
            logging.error("Unexpected response status on get "
                          "temporary oauth_token 200 != %s", response.status)
            self.exitErr = True

        responseData = self.parseResponse(response.data)
        if 'oauth_token' not in responseData:
            logging.error("OAuth temporary not found")
            self.exitErr = True

        self.tmpOAuthToken = responseData['oauth_token']

        logging.debug("Temporary OAuth token : %s", self.tmpOAuthToken)

    def handleTwoFactor(self):
        self.code = out.GetUserAuthCode()
        self.postData['tfa']['code'] = self.code
        response = self.loadPage(self.url['base'], self.url['tfa']+";jsessionid="+self.cookies['JSESSIONID'], "POST", self.postData['tfa'])
        if not response.location and response.status == 200:
            if self.incorrectCode < 3:
                #out.preloader.stop()
                #out.printLine('Sorry, incorrect two factor code')
                #out.preloader.setMessage('Authorize...')
                self.incorrectCode += 1
                return self.handleTwoFactor()
            else:
                logging.error("Incorrect two factor code")

        if not response.location:
            logging.error("Target URL was not found in the response on login")
            self.exitErr = True

    def login(self,username, password):
        response = self.loadPage(self.url['base'],
                                 self.url['login'],
                                 "GET",
                                 {'oauth_token': self.tmpOAuthToken})

        if response.status != 200:
            logging.error("Unexpected response status "
                          "on login 200 != %s", response.status)
            self.exitErr = True
            return

        if 'JSESSIONID' not in self.cookies:
            logging.error("Not found value JSESSIONID in the response cookies")
            self.exitErr = True
            return

        # get login/password
        #TODO: let's remove this storage - no need, i feel insecure about it
        self.username, self.password = username, password

        self.postData['login']['username'] = username
        self.postData['login']['password'] = password
        self.postData['login']['targetUrl'] = self.url['oauth'] % self.tmpOAuthToken
        response = self.loadPage(self.url['base'],
                                 self.url['login'] + ";jsessionid=" + self.cookies['JSESSIONID'],
                                 "POST",
                                 self.postData['login'])

        if not response.location and response.status == 200:
            if self.incorrectLogin < 3:
                self.incorrectLogin += 1
                return self.login(username, password)
            else:
                logging.error("Incorrect login or password")

        if not response.location:
            logging.error("Target URL was not found in the response on login")
            self.exitErr = True
            return

#TODO: reconsider this http status code -> what indicates 2 factor is needed?
#TODO: however this is only for premium users -> not so much of a concern?
        #if response.status == 302:
            # the user has enabled two factor auth
            #return self.handleTwoFactor()
            #self.exitErr = True
            #return

        logging.debug("Success authorize, redirect to access page")

        #self.allowAccess(response.location)

    def allowAccess(self):
        access = self.postData['access']
        access['oauth_token'] = self.tmpOAuthToken
        access['oauth_callback'] = "https://" + self.url['base']
        response = self.loadPage(self.url['base'],
                                 self.url['access'],
                                 "POST", access)

        if response.status != 302:
            logging.error("Unexpected response status on allowing "
                          "access 302 != %s", response.status)
            self.exitErr = True
            return

        responseData = self.parseResponse(response.location)
        if 'oauth_verifier' not in responseData:
            logging.error("OAuth verifier not found")
            self.exitErr = True
            return

        self.verifierToken = responseData['oauth_verifier']

        logging.debug("OAuth verifier token take")

        #self.getOAuthToken(verifier)

    def getOAuthToken(self):
        response = self.loadPage(self.url['base'],
                                 self.url['token'],
                                 "GET",
                                 self.getTokenRequestData(
                                     oauth_token=self.tmpOAuthToken,
                                     oauth_verifier=self.verifierToken))

        if response.status != 200:
            logging.error("Unexpected response status on "
                          "getting oauth token 200 != %s", response.status)
            self.exitErr = True
            return

        responseData = self.parseResponse(response.data)
        if 'oauth_token' not in responseData:
            logging.error("OAuth token not found")
            self.exitErr = True
            return

        logging.debug("OAuth token take : %s", responseData['oauth_token'])
        self.OAuthToken = responseData['oauth_token']
