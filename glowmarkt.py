#!/usr/bin/env python3

import requests, re
from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects
import logging as log

class Glowmarkt(object):
    URL='https://api.glowmarkt.com/api/v0-1/' # The API URL
    authObj = None
    headers = {
        'token': None,
        'applicationId': 'b0f1b774-a586-4f72-9edd-27ead8aa7a8d'
    }
    jwtCheck = re.compile('^([a-zA-Z0-9]+\.){2}([a-zA-Z0-9]+)$')
    appIdCheck = re.compile('^[a-f0-9-]+$')
    
    def authorise(self, u=None, p=None, t=None, appId=None):
        endpoint = self.URL + 'auth'
        reauth = False
        data = None
        response = None
        
        if not (u or p or t) and self.headers['token']:
            log.info('Glowmarkt.authorise(): reauthorising existing token')
            reauth = True
        elif t:
            assert self.jwtCheck.match(t), 'token (t) must be a valid JSON Web Token (JWT)'
            log.info('Glowmarkt.authorise(): reauthorising provided token')
            self.headers['token'] = t
            reauth = True
        else:
            assert len(u) > 0 and len(p) > 0, 'Username (u) and password (p) must be non-empty strings'
            log.info('Glowmarkt.authorise(): authorising user {}'.format(u))
            data = {'username': u, 'password': p}
        
        if appId:
            assert self.appIdCheck.match(appId), 'appId must be a hexadecimal string'
            self.headers['applicationId'] = appId
        
        try:
            if reauth:
                response = requests.get(endpoint,headers=self.headers)
            else:
                response = requests.post(endpoint,headers=self.headers,json=data)
            log.debug('Response from server: {}'.format(response.text))
            response.raise_for_status()
        except (ConnectionError, HTTPError, Timeout, TooManyRedirects) as e:
            if hasattr(e,'response') and e.response.status_code < 500:
                log.warning('Glowmarkt.authorise(): error {} - {}'.format(e.response.status_code,e.response.text))
                raise
            else:
                log.error('Glowmarkt.authorise(): server error {} - aborting!'.format(e.response.text))
                raise
        
        if not reauth:
            self.authObj = response.json()
            self.headers['token'] = self.authObj['token']

        log.debug('Glowmarkt.headers = {}'.format(self.headers))
        return True
    
    def __init__(self, u=None, p=None, t=None):
        self.authorise(u,p,t)

if __name__ == "__main__":
    import sys, argparse, pickle
    from pathlib import Path
    from xdg import xdg_config_home
    from getpass import getpass
    
    config = xdg_config_home() / 'glowmarkt.conf'
    gm = None
    
    p = argparse.ArgumentParser(description='Query the Glowmarkt API')
    p.add_argument('-v','--verbose',action='store_const',const=True,help='increase output verbosity')
    p.add_argument('-c','--config',type=str,nargs='?',help='load configuration from file CONFIG (defaults to {}'.format(config),default=None,const=str(config))
    p.add_argument('-u','--user',type=str,help='account username')
    p.add_argument('-t','--token',type=str,help='provide the token value from a previous authorisation')
    args = p.parse_args()
    
    if not (args.config or args.user or args.token):
        p.error('At least one option required: --config, --token or --user')
    
    if args.verbose:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
        log.info("Verbose output.")
    else:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.WARNING)
    
    log.debug('Called with arguments: {}'.format(vars(args)))
    
    if args.config == None: config = None
    else:
        # Check and load the congifuration file
        config = Path(args.config)
        try:
            if config.is_file():
                log.info('Found {}'.format(config))
                if config.stat().st_size == 0:
                    log.info('Configuration file {} is empty; ignoring'.format(config))
                else:
                    with config.open('rb') as f:
                        gm = pickle.load(f)
                    if gm:
                        log.debug('gm = {}'.format(vars(gm)))
                        gm.authorise()
                        log.info('Configuration loaded from file {}'.format(config))
            else:
                config.touch()
                log.info('Created new configuration file {}'.format(config))
        except Exception as e:
            log.warning('Configuration file ({}) error: {}'.format(config, e))
    
    # Instantiate or update the gm object from user provided details
    if args.token:
        log.info('Token provided: checking validity')
        if gm:
            gm.authorise(t=args.token)
        else:
            gm = Glowmarkt(t=args.token)
        log.info('Token validated! Ready to query API')
    if args.user:
        log.info('Username {} provided: getting password'.format(args.user))
        if gm and gm.token:
            gm.token = None
            log.info('Stored token cleared; reauthorising with username and password')
        for i in range(3):
            pwd = getpass('Password for {}:'.format(args.user))
            try:
                if gm:
                    gm.authorise(u=args.user,p=pwd)
                else:
                    gm = Glowmarkt(u=args.user,p=pwd)
            except AssertionError as e:
                log.error(str(e))
                continue
            except HTTPError as e:
                log.error('Password not accepted.')
                continue
            #except Exception as e:
            #    log.error('Some other error occurred: {}'.format(e))
            else:
                log.info('User {} authorised!'.format(args.user))
                break

    # Save configuration and clean up
    if config:
        if gm:
            try:
                with config.open('wb') as f:
                    pickle.dump(gm,f,pickle.HIGHEST_PROTOCOL)
            except Exception as e:
                log.warning('Couldn\'t save configuration to file {}: {}'.format(config, e))
        if config.is_file() and config.stat().st_size == 0:
            log.info('Removing empty configuration file {}'.format(config))
            try:
                config.unlink()
            except Exception as e:
                log.warning('Error deleting empty configuration file {}: {}'.format(config, e))